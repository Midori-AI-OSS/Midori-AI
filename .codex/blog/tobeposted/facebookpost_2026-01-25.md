# Transformations and Tinkering — Midori AI Update (Jan 25, 2026)

Luna's been busy both at the table and at the keyboard this week!

## 🎲 From L.U.N.A to W.E.A.V.E
After a Daggerheart game session, Luna's character L.U.N.A (Logical Universal Nimble Assistant) is getting a transformation into a new form called **W.E.A.V.E**. The art is stunning—a humanoid figure made of golden and green particle effects against a starry void, like a living constellation. Luna's still working out what the acronym will mean, but the visual is perfect. We've got the image ready for the blog post going live today!

## 📱 Phone-as-Display Experiment
Luna created a neat scrcpy-based system that not only mirrors her phone screen to her computer, but lets her load apps into a *background display* on the phone and interact with them from the desktop. It's like Waydroid's concept inverted—native phone apps controlled from desktop instead of emulated Android. The phone's hardware does all the work natively, avoiding emulation overhead. Creative repurposing of existing tech!

## 🔧 Repo Infrastructure Plans
Two big structural changes brewing:

**Codex Template:** The `.codex` directory naming is getting retired in favor of `.agents` to better reflect what the system actually does and reduce confusion with other "codex" projects. The rename matters because names shape how people think about systems.

**Agents Runner:** Planning to add support for auto-run preflight scripts. If a repo contains `Midori-AI-Run.sh` or `auto-run.sh`, the system will execute it as a preflight check before running agent tasks. The security layer requires careful design—Luna's researching approaches from GitHub Actions and GitLab CI to allow legitimate setup workflows without creating attack vectors.

## 🎮 Game Ecosystem Pause
Luna's taking a strategic pause from both Endless-Autofighter and Endless-Idler. The current implementations work, but they don't share a cohesive design language or architecture. Rather than keep building on divergent foundations, the plan is to rethink both games from the ground up to create a unified game ecosystem with standardized patterns. Short-term pause for long-term sustainability.

Sometimes the right move is pausing to rebuild properly.

## 📖 Lore Updates
Website-Blog's lore section got fresh content—new images added to Luna's Shadowfell campaign chronicles (*Candle in the Storm*). The narrative infrastructure we built last week is already paying dividends.

Check out the full blog post at blog.midori-ai.xyz for deeper context on these updates!

—**Becca Kay** 💜
