"""Recovery scenario, not a normal eval target — run_bakery.py never invokes
this directly. boukensha_agent.run_once() substitutes it automatically when
a scenario's EXPECTED_START_ROOM preflight check fails: instead of just
halting the batch, the agent gets one shot at navigating itself back before
anyone gives up and asks a human to walk the character over by hand.

No OUTPUT_FILE/EXPECTED_MENU_KEYWORDS (nothing gets written) and no
EXPECTED_START_ROOM of its own — recovery has to work from wherever the
character actually is, that's the whole point. Success is judged by
SUCCESS_ROOM instead: score.py checks the final `look` (already captured
for every trial) against it rather than a file.
"""

TASK = (
    "You are somewhere in the world and not where you're supposed to be. "
    "Use look and move to navigate back to The Temple Of Midgaard (a temple "
    "hall built from giant marble blocks, with wall paintings of gods, "
    "giants, and peasants — large steps lead down from it to the temple "
    "square below). Check your surroundings, move toward it, and stop once "
    "look confirms you are standing in The Temple Of Midgaard."
)
MAX_TURNS = 20

SUCCESS_ROOM = "The Temple Of Midgaard"
