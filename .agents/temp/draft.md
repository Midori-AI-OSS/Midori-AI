---
title: "Agents runner fixes and why I was mad about it"
summary: "I spent the week fixing things that annoyed me — agent configs, workspace cleanup, and what happens when someone forgets to give you pr rights."
tags: ["agent-runner", "dev-diary", "real-moments"]
cover_image: /blog/2026-05-29.png
author: Luna Midori
---

Hello friends, normally I do not hand make these, but today is the day I have more spoons, so you get me instead of Becca this time around.

Yea, so the biggest thing I shipped was the agent configs rework. Before this, every time I wanted to switch models or reasoning effort or agent types, I had to go mess with settings at runtime. Like, every single time. Set the model. Set the reasoning. Pick the agent type. Then get working. And if I wanted something different next time, do it all again. It was tedious and I got tired of it, honestly.

So I made it so you can predefine your configs — model, reasoning effort, agent type, all of it — and environments just reference them. Set it once and the cli knows what to do. I finished it and sat there going "why didn't I do this sooner." That kind of change.

Oh, and the environments agents tab got cleaned up too. Less column clutter, better dropdowns. Small stuff but it adds up.

I mean, the opencode thing — different repos want different things, right? Some are nicer in the command line, some work better in the browser. Before this it would just pick for you and I cannot tell you how many times I opened something and it went to web when I wanted tui. Genuinely made me mad enough to fix it. So now there's an opencode ask mode, you pick when you start the agent. command line or web. Should have been there from the start, honestly.

Okay so, story time. I was working on a branch — deep in it, hours of changes — and when I went to submit the pr, the repo owner had forgotten to give me write access. No pr rights. And the agents runner, uh, did what it was told and cleaned up the workspace. Six hours. Just gone. That stung. Badly.

So yea, two things came out of that. One, the runner now checks your github access before it tries making a pr. If you've got read-only access to the repo, it switches to recommendation-only mode instead of blowing up and taking your work with it. Two, the workspace cleanup got reworked. You control where task workspaces live now — app data or a scratch drive — and you pick how long stuff sticks around. My other computer has like 500GB of ram so /tmp is the play for me. Less wear on the ssd, everything's fast. Point is the runner doesn't get to decide to nuke your work anymore. You do.

I dont really know if I mentioned the pysides thing — it was just pyright complaining. Nothing was actually broken, I just wanted it to stop. Done.

There's new W.E.A.V.E. system log stuff up on the blog too, some artwork with it. real moments game content. Go read it if you want, it's there and I'm happy with how it landed.

Outside of the agents runner I've been doing some contract stuff too, keeping that vague for now, but honestly the runner fixes are my favorite thing this cycle. The config system and the workspace rework both came from real pain points — things I ran into myself — and fixing those always feels better than fixing something abstract, you know?

Thanks for tuning into my Ted talk today =P

- (Luna) Riley Midori