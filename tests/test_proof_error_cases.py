import re
import textwrap

import pytest

from deutil.proof import Proof
from deutil.rules import ProofError


def run_markdown(markdown: str) -> None:
    lines = textwrap.dedent(markdown).strip().splitlines()
    proof = Proof.from_markdown(lines)
    proof.check()


def assert_proof_error(markdown: str, pattern: str) -> None:
    with pytest.raises(ProofError, match=pattern):
        run_markdown(markdown)


def assert_syntax_error(markdown: str, pattern: str) -> None:
    with pytest.raises(SyntaxError, match=pattern):
        run_markdown(markdown)


@pytest.mark.parametrize(
    ("markdown", "pattern"),
    [
        (
            """
            | 1. A  bogus-rule
            """,
            r"Unknown justification",
        ),
        (
            """
            | 1. Fx'  premise
            """,
            r"arbitrary terms are not in scope",
        ),
        (
            """
            | 1. A  premise
            |-
            | 2. A  repeat: 9
            """,
            r"Line 9 not found",
        ),
        (
            """
            |-
            | | 1. A  premise
            | |-
            | | 2. B  premise
            | 3. B  repeat: 1
            """,
            r"Line 1 is not accessible",
        ),
        (
            """
            |-
            | | 1. A  assumption for C.D.
            | |-
            | | 2. B  premise
            | 3. A  premise
            | | 4. C  assumption for C.D.
            | |-
            | | 5. C  premise
            | 6. (A -> B)  C.D. 1-5
            """,
            r"not in the same subproof",
        ),
        (
            """
            |-
            | | 1. A  assumption for C.D.
            | |-
            | | 2. B  premise
            | | 3. C  premise
            | 4. (A -> B)  C.D. 2-3
            """,
            r"not the start of a subproof",
        ),
        (
            """
            |-
            | | 1. A  assumption for C.D.
            | |-
            | | 2. B  premise
            | | 3. C  premise
            | 4. (A -> B)  C.D. 1-2
            """,
            r"not the end of a subproof",
        ),
        (
            """
            | 1. (A -> B)  premise
            |-
            | 2. B  MP: 1
            """,
            r"Unknown justification",
        ),
        (
            """
            | 1. (A -> B)  premise
            | 2. A  premise
            |-
            | 3. ~B  MP: 1, 2
            """,
            r"No matching rule found for ModusPonens",
        ),
        (
            """
            | 1. A  premise
            |-
            | 2. C  repeat: 1
            """,
            r"No matching rule found for Repeat",
        ),
        (
            """
            |-
            | | 1. A  assumption for C.D.
            | |-
            | | 2. B  premise
            | 3. A  C.D. 1-2
            """,
            r"Conclusion of conditional derivation must be an implication",
        ),
        (
            """
            |-
            | | 1. A  assumption for C.D.
            | |-
            | | 2. B  premise
            | 3. (C -> B)  C.D. 1-2
            """,
            r"First premise of conditional derivation must match antecedent",
        ),
        (
            """
            |-
            | | 1. A  assumption for C.D.
            | |-
            | | 2. B  premise
            | 3. (A -> C)  C.D. 1-2
            """,
            r"Last premise of conditional derivation must match consequent",
        ),
        (
            """
            |-
            | | 1. A  premise
            | | 2. B  premise
            | |-
            | | 3. ~B  premise
            | 4. C  I.D. 1-3
            """,
            r"Indirect derivation must have exactly one assumption",
        ),
        (
            """
            |-
            | | 1. ~A  assumption for I.D.
            | |-
            | | 2. B  premise
            | 3. A  I.D. 1-2
            """,
            r"Indirect derivation must have at least 2 statements",
        ),
        (
            """
            |-
            | | 1. ~A  assumption for I.D.
            | |-
            | | | 2. B  assumption for C.D.
            | | |-
            | | | 3. C  premise
            | | 4. ~B  premise
            | 5. A  I.D. 1-4
            """,
            r"Second-last line of indirect derivation cannot be a subproof",
        ),
        (
            """
            |-
            | | 1. ~A  assumption for I.D.
            | |-
            | | 2. B  premise
            | | 3. C  premise
            | 4. A  I.D. 1-3
            """,
            r"Last premise of indirect derivation must be a negation",
        ),
        (
            """
            |-
            | | 1. ~A  assumption for I.D.
            | |-
            | | 2. B  premise
            | | 3. ~C  premise
            | 4. A  I.D. 1-3
            """,
            r"must be the negation of the second-last premise",
        ),
        (
            """
            |-
            | | 1. A  assumption for C.D.
            | |-
            | | 2. B  premise
            | | 3. ~B  premise
            | 4. C  I.D. 1-3
            """,
            r"First premise of indirect derivation must be a negation",
        ),
        (
            """
            |-
            | | 1. ~A  assumption for I.D.
            | |-
            | | 2. B  premise
            | | 3. ~B  premise
            | 4. C  I.D. 1-3
            """,
            r"must be the negation of the conclusion",
        ),
        (
            """
            | 1. A  premise
            |-
            | 2. B  UI: 1
            """,
            r"Premise of universal instantiation must be a universal quantifier",
        ),
        (
            """
            | 1. \\VxFx  premise
            |-
            | 2. (A ^ B)  UI: 1
            """,
            r"No suitable term found to replace",
        ),
        (
            """
            | 1. A  premise
            |-
            | 2. B  EG: 1
            """,
            r"Conclusion of existential generalisation must be an existential quantifier",
        ),
        (
            """
            | 1. Fa  premise
            |-
            | 2. \\ExGx  EG: 1
            """,
            r"No suitable term found to replace",
        ),
        (
            """
            | 1. A  premise
            |-
            | 2. B  EI: 1
            """,
            r"Premise of existential instantiation must be an existential quantifier",
        ),
        (
            """
            | 1. \\ExFx  premise
            |-
            | 2. (A ^ B)  EI: 1
            """,
            r"No suitable term found to replace",
        ),
        (
            """
            |-
            | | 1. Fx  premise
            | |-
            | | 2. Gx  premise
            | 3. (Fx -> Gx)  U.D. 1-2
            """,
            r"Conclusion of universal derivation must be a universal quantifier",
        ),
        (
            """
            |-
            | | 1. A  assumption for C.D.
            | |-
            | | 2. Fx  premise
            | 3. \\VxFx  U.D. 1-2
            """,
            r"must have an arbitrary term",
        ),
        (
            """
            |-
            | | [x']
            | |-
            | | 1. Gx'  premise
            | 2. \\VxHx  U.D. 1-1
            """,
            r"must match body of conclusion",
        ),
    ],
)
def test_proof_errors(markdown: str, pattern: str) -> None:
    assert_proof_error(markdown, pattern)


@pytest.mark.parametrize(
    ("markdown", "pattern"),
    [
        (
            """
            | 1 A  premise
            """,
            r"Invalid proof line",
        ),
        (
            """
            | 1. A premise
            """,
            r"Invalid proof line",
        ),
        (
            """
            | 1. (A -> B  premise
            """,
            r"Error parsing expression",
        ),
        (
            """
            | 1. (  premise
            """,
            r"Unexpected end of expression|Error parsing expression",
        ),
        (
            """
            | [x']
            | 1. Fx'  premise
            """,
            r"Arbitrary terms can only be defined in subproofs",
        ),
        (
            """
            |-
            | | 1. A  premise
            | | [x']
            | |-
            | | 2. A  repeat: 1
            | 3. (A -> A)  C.D. 1-2
            """,
            r"must be the first line of a subproof",
        ),
        (
            """
            |-
            | | [x']
            | | [y']
            | | 1. Fx'  premise
            """,
            r"Multiple arbitrary terms defined in the same proof",
        ),
    ],
)
def test_syntax_errors(markdown: str, pattern: str) -> None:
    assert_syntax_error(markdown, pattern)
