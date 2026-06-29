## Who to follow on X

X has no open RSS, but Sift can now follow X handles through a **bridge** — run
`sift add-x <handle>` (see the [guide](guide.html)). The accounts below are worth
following; **scanned** means Sift already pulls it, via a blog/newsletter feed or
the X bridge.

### Researchers & builders

- [Andrej Karpathy](https://x.com/karpathy) — foundational explainers; ex-OpenAI/Tesla. *(blog + X scanned)*
- [Andrew Ng](https://x.com/AndrewYNg) — DeepLearning.AI, applied AI.
- [Jim Fan](https://x.com/DrJimFan) — NVIDIA, embodied agents & robotics. *(X scanned)*
- [Yann LeCun](https://x.com/ylecun) — Meta chief AI scientist. *(X scanned)*
- [Simon Willison](https://x.com/simonw) — LLM tooling, hands-on. *(blog scanned)*
- [Sebastian Raschka](https://x.com/rasbt) — model architecture & training. *(Ahead of AI scanned)*

### Agents, tooling & engineering

- [swyx](https://x.com/swyx) — AI engineering. *(Latent Space scanned)*
- [Gergely Orosz](https://x.com/GergelyOrosz) — SDLC & dev tooling. *(Pragmatic Engineer scanned)*
- [Ethan Mollick](https://x.com/emollick) — real enterprise AI adoption. *(One Useful Thing scanned)*

### Infra, chips & analysis

- [Dylan Patel](https://x.com/dylan522p) — chips, datacenters, energy. *(SemiAnalysis scanned)*
- [Nathan Lambert](https://x.com/natolambert) — model & RLHF research. *(Interconnects scanned)*
- [Jack Clark](https://x.com/jackclarkSF) — policy & capabilities. *(Import AI scanned)*

### Labs (official)

- [OpenAI](https://x.com/OpenAI) &middot; [Anthropic](https://x.com/AnthropicAI) &middot;
  [Google DeepMind](https://x.com/GoogleDeepMind) &middot; [Meta AI](https://x.com/AIatMeta) &middot;
  [Hugging Face](https://x.com/huggingface)

## Wanted, but no working feed right now

These fit the profile but don't have a usable RSS feed at the moment — revisit later:

- **The Batch** (Andrew Ng / DeepLearning.AI) — feed URL currently 404s.
- **arXiv cs.LG / cs.CL** — the `rss.arxiv.org` endpoints returned empty on the
  last check (the same intermittency that hit cs.AI). Worth re-adding when they
  recover.

> **How X gets in:** `sift add-x <handle>` routes the handle through the bridge in
> `config.toml` (`[x] bridge_url`). Public Nitter instances are unstable — for
> reliability, self-host Nitter/RSSHub or use an RSS.app feed. The official X API
> is the heavyweight alternative (pay-per-use reads + auth) and is overkill here.
