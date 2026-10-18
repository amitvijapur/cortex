# Help test the first-run experience

Try the [first-run guide](first-run.md) in a small project. The first useful feedback is whether someone can install Cortex, understand what it does and complete one real routed task without live help.

This is a feedback procedure, not evidence that external testing has already happened. Automated CLI fixtures do not establish a working live integration with every advertised host.

## What to try

- [ ] Find the purpose of Cortex and the first command from the README.
- [ ] Choose Claude Code's guided path or a documented manual host path.
- [ ] Install without losing existing instructions, skills or registry edits.
- [ ] Identify the canonical protocol, CLI and selected state root.
- [ ] Complete the bounded review in the first-run guide with a declared route and recorded outcome.
- [ ] Read the resulting history and explain the route in your own words.
- [ ] Find the update and removal instructions without maintainer help.

Stop if a step fails. Keep the exact error and report it rather than deleting personalized files to force installation. A partial trial is useful feedback.

## Report your experience

Open an [onboarding feedback issue](https://github.com/amitvijapur/cortex/issues/new?template=onboarding-feedback.yml), or a [blank issue](https://github.com/amitvijapur/cortex/issues/new) if the form is unavailable. Include:

- The Cortex tag or commit, OS, Python version, host and host version.
- Whether setup was guided or manual, and whether the state root was default or custom.
- The last successful step, exact failing command and sanitized output.
- Whether the agent declared a route and whether `show --last 3` included the right task and outcome.
- What you expected, what happened and where an explanation was missing.
- Any maintainer help you needed, so it does not get counted as unaided setup.

Do not attach full personal routing logs, inventories, tokens or private project text. A short redacted excerpt is enough. Routing quality feedback should include the concrete task, available capabilities and why another route would have been preferable. A completed installation does not establish token savings or faster delivery.

## Maintainer follow-up

Start with a small group of developers who already use coding agents. Ask them to follow the public guide as written. Record actual attempts by host and revision, including failed and assisted trials. Fix blockers before inviting a larger group.

Useful initial observations are the step where people stop, whether they finish unaided, which host paths fail and whether the declared route matches the work performed. Do not turn a small convenience sample into a general success-rate or performance claim. Publish compatibility results only with their tested versions and limits.
