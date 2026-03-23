# Changelog

## 2026-03-23

### Improved carousel hook quality in Claude scoring prompt

Updated the `ANGLE` instruction in the Claude evaluation prompt (`evaluate_articles_with_claude`) to produce structured, scroll-stopping hooks instead of generic angles.

**What changed:**
- The ANGLE field now requires Claude to identify the psychological trigger driving the hook (Curiosity, FOMO, Disbelief, Defensiveness, Relief, or Greed)
- Hooks must be written with intentional line breaks using "/" to indicate slide breaks
- Each line is capped at 7 words; maximum 3 lines total
- Output format: `"[TRIGGER: Disbelief] The last Laker to score 60 / was Kobe. / In his final game."`

**Why:** The previous instruction ("A specific carousel hook or angle that would perform well") produced headline-style copy. The new rules enforce the punchy, line-broken format that actually performs on Instagram and TikTok carousels.
