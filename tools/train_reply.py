# Train Laya's decision layers for reply.py's question ("did the grandkid understand the kept word?") on
# tools/data/reply_train.jsonl (tools/make_reply_data.py). Laya's shared encoder stays frozen, and only the trained
# layers are saved (models/reply_head.pt), so Laya's other decisions (decide.py) don't change.
#   python tools/train_reply.py                 # the whole decision head (~26M weights, ~53 MB)
#   python tools/train_reply.py --train last    # only the last transformer layer + scorer (~13M, ~26 MB)
#   python tools/train_reply.py --train scorer  # only the final scoring layer: didn't learn at all (stuck at 44%)
# A tenth of the training *words* are held out to pick the best epoch; tools/check_reply.py then tests on
# hand-written examples with other words again.
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
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--lr", type=float, default=None)
    p.add_argument("--batch", type=int, default=16)
    args = p.parse_args()
    lr = args.lr or {"scorer": 1e-3, "last": 2e-4, "all": 1e-4}[args.train]

    rows = [json.loads(line) for line in open(os.path.join(ROOT, "tools", "data", "reply_train.jsonl"))]
    words = sorted({r["word"].lower() for r in rows})
    random.Random(0).shuffle(words)
    val_words = set(words[: len(words) // 10])
    train = [r for r in rows if r["word"].lower() not in val_words]
    val = [r for r in rows if r["word"].lower() in val_words]
    print(f"{len(train)} training examples, {len(val)} validation ({len(val_words)} held-out words); training {args.train}")

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
    q = agent._to_internal(QUESTION)
    target = {lab: i for i, lab in enumerate(LABELS)}  # QUESTION's criteria are in LABELS order

    # The encoder is frozen, so run it once per batch of examples and keep its output (on the CPU, half precision);
    # each epoch then only runs the small head.
    def cache(data):
        out = []
        start = time.monotonic()
        for i in range(0, len(data), args.batch):
            chunk = data[i:i + args.batch]
            b = encode(agent, [state(r["line"], r["word"], r["means"], r["reply"]) for r in chunk], q)
            h = run_encoder(model, b, device).half().cpu()
            out.append((b, h, torch.tensor([target[r["label"]] for r in chunk])))
            if device.type == "mps":
                torch.mps.empty_cache()
        print(f"  encoded {len(data)} examples in {time.monotonic() - start:.0f} s")
        return out

    def forward(b, h):
        return run_head(model, head, b, device, h=h.to(device).float())

    def accuracy(cached):
        head.eval()
        right = total = 0
        with torch.no_grad():
            for b, h, y in cached:
                right += (forward(b, h).argmax(-1).cpu() == y).sum().item()
                total += len(y)
        return right / total

    train, val = cache(train), cache(val)
    best, best_state = accuracy(val), None
    print(f"before training: validation {best:.1%}", flush=True)
    random.seed(1)
    for epoch in range(args.epochs):
        head.train()
        start, total, n = time.monotonic(), 0.0, 0
        random.shuffle(train)
        for b, h, y in train:
            loss = torch.nn.functional.cross_entropy(forward(b, h), y.to(device))
            opt.zero_grad()
            loss.backward()
            opt.step()
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
    os.makedirs(os.path.dirname(HEAD_PATH), exist_ok=True)
    torch.save(best_state, HEAD_PATH)
    print(f"saved the best epoch (validation {best:.1%}) to {os.path.relpath(HEAD_PATH, ROOT)} "
          f"({os.path.getsize(HEAD_PATH) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
