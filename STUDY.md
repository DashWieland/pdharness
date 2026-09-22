# The Stage 2 study: does "limited prompting" generalise?

*Stage 2 of the harness's public plan. Bring your own agent, three to five
outside participants, field logs. Near-zero infrastructure. The go or no-go
for a hosted version.*

## The question

One person, with this bank loaded and years of taste, built ember in an
afternoon with limited prompting. Does a stranger, with their own agent and
this package, get anywhere near that? If yes, a hosted version is worth
paying for per user. If no, the failures say what the bank still lacks, and
that is cheaper to learn now.

## Participants

Three to five people, deliberately mixed:

- at least one who has never opened Pure Data;
- at least one who uses Claude Code or another agent daily;
- at least one musician who is neither.

They bring their own machine and agent. We ask for an hour, a description in
their own words, and a log.

## What each participant does

1. Installs: Pd, `pdharness`, registers the server, runs `doctor`. **The
   install is measured too.** Time and every snag go in the log.
2. Describes an instrument to their agent in a sentence or two, in their own
   words. We do not translate.
3. Lets the agent build it. They answer its questions and react to renders,
   nothing more.
4. Opens the `.pd` in Pd and plays it.
5. Sends back the field log the agent wrote, with their own section filled
   in, and the instrument files if they like.

## What we measure (per participant)

| Measure | Why |
|---|---|
| Install time and snags | the first floor to lower is the one before the first prompt |
| Time to first sound, time to done | the promise is "an afternoon," not "a week" |
| Render iterations, silent or broken renders | is the loop converging, and is the tooling catching Pd's dominant failure |
| Intent gap, classified | vocabulary, perception, construction: each points at a different fix |
| Modules adopted and rejected | is the library the right library |
| Playable by them, in Pd | the interaction bugs headless verification cannot see |
| Their verdict, verbatim | would they play it again; what it felt like |

## Go or no-go

**Go** for a hosted version if, of the participants who got through the
install, most reach a playable instrument they would play again inside two
hours, and the failures are library gaps (a missing module, a missing
measurand) rather than reasoning gaps (the agent could not turn a diagnosis
into an edit). Library gaps are fixable by adding to the bank; reasoning gaps
are not fixed by hosting.

**No-go, for now,** if the install defeats people, if the loop does not
converge without a facilitator, or if the results are instruments nobody
wants to touch twice. Then the work is on the bank and the tools, and the
next test is another round of this study, not a server.

## What goes back into the bank

Every log's Lessons section, anonymised. Requests for measurands and modules
become briefs for the library. Wrong or missing facts in the skill are fixed
immediately. The instruments, with permission, join the examples.

## Consent and privacy

Participants are told the log goes into a public knowledge bank, anonymised
to a first name or role, and that nothing is recorded beyond what the agent
writes and what they choose to add. They can withdraw the log at any time
before it is published.
