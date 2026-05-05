import pytest
import textwrap

from deutil.proof import Proof

@pytest.mark.parametrize(
    "markdown",
    [
        """
        | 1. ~\\ExFx               premise
        |-
        | | [x']
        | |-
        | | | 2. ~~Fx'            assumption for indirect derivation
        | | |-
        | | | 3. Fx'              double negation, 2
        | | | 4. \\ExFx            existential generalisation, 3
        | | | 5. ~\\ExFx           repeat, 1
        | | 6. ~Fx'               indirect derivation, 2-5
        | 7. \\Vx~Fx               universal derivation, 2-6
        """,
    ]
)
def test_all_rule_success_cases(markdown: str) -> None:
    lines = textwrap.dedent(markdown).strip().splitlines()
    proof = Proof.from_markdown(lines)
    proof.check()

