# Field-test protocol

A field test is an end-to-end run of the premise: a person describes an
instrument in a sentence or two, an agent with this bank and these tools
builds it, and the person plays it. The log is the product of the session
as much as the instrument is.

## For the facilitator (who may be the participant)

1. **Setup.** A fresh agent session in a directory the participant owns,
   with `pdharness serve` registered and `pdharness doctor` reporting ok.
   Do not brief the session beyond that; the bank is the briefing, and the
   bank is what is being tested.
2. **The request.** The participant describes, in their own words, something
   they would want to play. A sentence or two of vibe is the point: "rain on
   a tin roof I can speed up," "a fat bass I can wobble," "my uncle's banjo
   from the porch." Pass their words through verbatim; do not translate them
   into synthesis terms.
3. **Hands off.** The facilitator does not type during the build. The
   participant may answer the agent's questions and react to renders.
4. **Listen.** The agent renders a demo `.wav` during the loop; the real test
   is the participant opening the `.pd` in Pd and playing it.
5. **Afterwards.** The agent writes its own log from the template. The
   facilitator adds the participant's-eye view: what they expected, what they
   got, verbatim reactions, whether they would play it again.

## What is measured

- **Convergence:** a working instrument, in how many render iterations.
- **Silent failures:** how many iterations rendered silent or broken, and why.
- **Intent gap:** where the result diverged from what was meant, classified
  as vocabulary (their words to synthesis), perception (the analyzer could
  not hear the quality that mattered), or construction (knew what to change,
  not how).
- **Playability:** could a human play it in vanilla Pd? Interaction bugs are
  invisible to headless verification; this is where they surface.
- **Time:** from description to first sound, and to done.
- **Modules:** which verified parts were adopted, which rejected, and why.

## What goes back

The log, anonymised: no names beyond a first name or role, no recordings of
people unless they agree, the instrument files if the participant is happy
to share them. The lessons section is the part the bank grows from.
