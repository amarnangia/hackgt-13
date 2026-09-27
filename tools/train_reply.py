# Train Laya's decision layers for reply.py's question ("did the grandkid understand the kept word?") on
# tools/data/reply_train.jsonl (tools/make_reply_data.py). Laya's shared encoder stays frozen, and only the trained
# layers are saved (models/reply_head.pt), so Laya's other decisions (decide.py) don't change.
#   python tools/train_reply.py                 # the whole decision head (~26M weights, ~53 MB)
#   python tools/train_reply.py --train last    # only the last transformer layer + scorer (~13M, ~26 MB)
#   python tools/train_reply.py --train scorer  # only the final scoring layer: didn't learn at all (stuck at 44%)
#   python tools/train_reply.py --out /tmp/try.pt --lr 3e-4   # try settings without replacing the saved head
# A tenth of the training *words* are held out to pick the best epoch; tools/check_reply.py then tests on
# hand-written examples with other words again.
# The encoder runs once per example; every epoch then reshuffles the examples into new batches. (The first version
# cached fixed batches of neighbouring rows, i.e. the same ~2 words per batch every epoch, and only reached 72% on
# its own training data.)
import argparse
import json
import os
import random
import sys
import time

import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reply import HEAD_PATH, LABELS, QUESTION, encode, new_head, run_encoder, run_head, state  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--train", choices=["scorer", "last", "all"], default="all")
    p.add_argument("--epochs", type=int, default=25)
    p.add_argument("--lr", type=float, default=None)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", default=HEAD_PATH, help="where to save the best epoch")
    p.add_argument("--data", nargs="+", default=[os.path.join("tools", "data", f) for f in ("reply_train.jsonl", "reply_train_2.jsonl")],
                   help="training files (make_reply_data.py); held-out words are picked across all of them")
    args = p.parse_args()

    rows = [json.loads(line) for path in args.data for line in open(os.path.join(ROOT, path))]
    words = sorted({r["word"].lower() for r in rows})
    random.Random(0).shuffle(words)
    val_words = set(words[: len(words) // 10])
    train = [r for r in rows if r["word"].lower() not in val_words]
    val = [r for r in rows if r["word"].lower() in val_words]
    print(f"{len(train)} training examples, {len(val)} validation ({len(val_words)} held-out words); training {args.train}")
    train_head(train, val, QUESTION, LABELS, lambda r: state(r["line"], r["word"], r["means"], r["reply"]), args)


def train_head(train, val, question, labels, to_state, args):
    """Train a copy of Laya's decision layers on (to_state(row), row["label"]) rows; save the best epoch on `val`
    to args.out. Shared with tools/train_sayings.py."""
    out_path = args.out
    lr = args.lr or {"scorer": 1e-3, "last": 3e-4, "all": 2e-4}[args.train]
    import laya
    agent = laya.load("convaiinnovations/laya", device="mps" if torch.backends.mps.is_available() else "cpu")
    model, device = agent.model, agent.device
    for param in model.parameters():
        param.requires_grad = False
    head = new_head(model).to(device).float()
    # No dropout: the Mac GPU can't do it inside attention. Weight decay and keeping the best epoch on held-out words
    # guard against overfitting instead.
    for module in head.modules():
        if isinstance(module, torch.nn.Dropout):
            module.p = 0.0
        if isinstance(module, torch.nn.MultiheadAttention):
            module.dropout = 0.0
    trainable = {"scorer": ["scorer."], "last": ["scorer.", f"layers.{len(head['layers']) - 1}."], "all": [""]}[args.train]
    for name, param in head.named_parameters():
        param.requires_grad = any(name.startswith(t) for t in trainable)
    params = [param for param in head.parameters() if param.requires_grad]
    print(f"trainable weights: {sum(x.numel() for x in params) / 1e6:.1f}M, lr {lr}")
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=0.01)
    sched = None  # set once we know how many batches an epoch has
    q = agent._to_internal(question)
    target = {lab: i for i, lab in enumerate(labels)}  # the question's criteria are in `labels` order

    # The encoder is frozen, so run it once per example and keep its output (on the CPU, half precision); each epoch
    # then only runs the small head, on freshly shuffled batches.
    from laya.common import collate_items

    def cache(data):
        out = []
        start = time.monotonic()
        for i in range(0, len(data), args.batch):
            chunk = data[i:i + args.batch]
            groups = [agent._encode_state(to_state(r), ["q"], {"q": q}) for r in chunk]
            b = collate_items(groups, agent.tok.pad_token_id)
            h = run_encoder(model, b, device).half().cpu()
            for j, (g, r) in enumerate(zip(groups, chunk)):
                n_tok = int(b["attention_mask"][j].sum())
                out.append((g, h[j, :n_tok].clone(), target[r["label"]]))
            if device.type == "mps":
                torch.mps.empty_cache()
        print(f"  encoded {len(data)} examples in {time.monotonic() - start:.0f} s")
        return out

    def batches(cached, shuffle):
        order = list(range(len(cached)))
        if shuffle:
            rng.shuffle(order)
        for i in range(0, len(order), args.batch):
            items = [cached[k] for k in order[i:i + args.batch]]
            b = collate_items([g for g, _, _ in items], agent.tok.pad_token_id)  # Laya pads on the right
            h = torch.zeros(len(items), b["input_ids"].shape[1], items[0][1].shape[-1], dtype=torch.float16)
            for j, (_, hj, _) in enumerate(items):
                h[j, :len(hj)] = hj
            yield b, h, torch.tensor([y for _, _, y in items])

    def forward(b, h):
        return run_head(model, head, b, device, h=h.to(device).float())

    def accuracy(cached):
        head.eval()
        right = 0
        with torch.no_grad():
            for b, h, y in batches(cached, shuffle=False):
                right += (forward(b, h).argmax(-1).cpu() == y).sum().item()
        return right / len(cached)

    rng = random.Random(args.seed)
    torch.manual_seed(args.seed)
    train, val = cache(train), cache(val)
    steps = args.epochs * -(-len(train) // args.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=0.1)
    best, best_state = accuracy(val), None
    print(f"before training: validation {best:.1%}", flush=True)
    for epoch in range(args.epochs):
        head.train()
        start, total, n = time.monotonic(), 0.0, 0
        for b, h, y in batches(train, shuffle=True):
            loss = torch.nn.functional.cross_entropy(forward(b, h), y.to(device))
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            total, n = total + loss.item() * len(y), n + len(y)
        acc = accuracy(val)
        print(f"epoch {epoch + 1}: loss {total / n:.3f}, validation {acc:.1%} ({time.monotonic() - start:.0f} s)", flush=True)
        if acc > best:
            best = acc
            best_state = {k: v.detach().half().cpu() for k, v in head.state_dict().items()
                          if any(k.startswith(t) for t in trainable)}
        if device.type == "mps":
            torch.mps.empty_cache()
    if best_state is None:
        print("training never beat the untrained head; nothing saved")
        return
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    torch.save(best_state, out_path)
    print(f"saved the best epoch (validation {best:.1%}, training {accuracy(train):.1%} at the end) to {out_path} "
          f"({os.path.getsize(out_path) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
