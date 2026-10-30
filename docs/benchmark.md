# Synthetic benchmark

20 seeds per row. Bad physics = a late unmodelled push the early frames cannot predict.

| Motion | Noise (mm) | Dropped frames | Median g error | Certified (good physics) | Certified (bad physics) |
|---|---|---|---|---|---|
| projectile | 2 | 0% | 0.0% | 100% | 0% |
| projectile | 5 | 0% | 0.1% | 100% | 0% |
| projectile | 5 | 20% | 0.1% | 100% | 0% |
| projectile | 10 | 20% | 0.3% | 100% | 0% |
| bounce | 2 | 0% | 0.2% | 100% | 0% |
| bounce | 5 | 0% | 0.8% | 100% | 0% |
| bounce | 5 | 20% | 0.8% | 95% | 0% |
| bounce | 10 | 20% | 1.3% | 85% | 0% |
| pendulum | 2 | 0% | 0.0% | 100% | 0% |
| pendulum | 5 | 0% | 0.1% | 100% | 0% |
| pendulum | 5 | 20% | 0.1% | 100% | 0% |
| pendulum | 10 | 20% | 0.1% | 100% | 0% |

## Rendered clips with known truth (end to end, live Muse Spark and SAM 3.1)

These are rendered, not filmed: photographic-ish wall, motion blur, noise, H.264, 1280x720 at 30 fps, 10 cm ball, g = 9.81 m/s2. They test the whole pipeline but are not real footage. Real free clips I tried (pendulum, gym ball, juggling, tennis, soccer, slow-motion throw) were all refused by the trust check, and none was certified wrongly.

| Clip | What it should do | Result |
|---|---|---|
| bounce (restitution 0.75) | certify | certified: e 0.748, g 9.71 (1% off) |
| pendulum (L 1.0 m, 25 deg, period 2.006 s) | certify | certified: L 1.028 m, period 2.027 s (1% off), g 10.08 (2.8% off) |
| toss | certify | certified: g 8.94 (9% off; the SAM box includes motion blur, which inflates the ball's apparent size) |
| camera shake | refuse | refused: the camera moved |
| slow motion (1/3 speed) | refuse | refused: g reads 1.12, and the clip has under one swing |

Caveats found by this run:
- The language model guessed a 6.7 cm tennis ball for a 10 cm ball. With that guess toss and pendulum read g of 6.0 and 6.8, and the g-plausibility gate refused them. The reported numbers above use `--size 0.10`.
- With three keyframes the model called the bounce clip a plain drop. The identifier now gets six evenly spaced frames and calls it a bounce with no override.

