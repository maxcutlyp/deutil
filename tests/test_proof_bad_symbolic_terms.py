import pytest
import textwrap

from deutil.proof import Proof
from deutil.rules import ProofError

def assert_fail(markdown: str, pattern: str) -> None:
    lines = textwrap.dedent(markdown).strip().splitlines()
    proof = Proof.from_markdown(lines)

    with pytest.raises(ProofError, match=pattern):
        proof.check()

@pytest.mark.xfail
def test_already_defined_ei() -> None:
    assert_fail(
        """
        | 1. Fa         premise
        | 2. \\ExGx     premise
        |-
        | 3. Ga         existential instantiation, 2
        """,
        "already in use",
    )

@pytest.mark.xfail
def test_undefined_ui() -> None:
    assert_fail(
        """
        | 1. \\VxFx  premise
        |-
        | 2. Fa      universal instantiation, 1
        """,
        'not in scope',
    )

