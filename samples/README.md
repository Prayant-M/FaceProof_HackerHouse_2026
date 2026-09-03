# samples/

Put your probe image here, e.g. `samples/me.jpg`.

**Probe images are gitignored on purpose.** Do not commit photographs of people
to a public repository — not yours, and definitely not anyone else's.

## Choosing a probe

FaceProof only produces evidence when the live search actually finds the face.
That means the subject needs a public image footprint. In practice:

| Subject | Expected result |
|---|---|
| You, with public posts on Instagram / LinkedIn / X | usually works |
| You, with no public photos anywhere | zero hits — this is correct behaviour, not a bug |
| A public figure | reliably works; use this to prove the pipeline |

Test this **early**. Discovering on the last day that your face returns nothing
is the single most common way this project fails.

## Consent

`faceproof run` requires `--i-have-consent`. Only pass it when the subject is
you, someone who agreed, or a public figure whose posts are already public.
