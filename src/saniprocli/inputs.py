import sys

from saniprocli.abc import InputStrategy


class OnelineInputStrategy(InputStrategy):
    """Represents the method to get a user input per prompt
    in interactive mode.
    It consumes just one line to get the input by a user."""

    def __init__(self, ps1: str | None = "") -> None:
        super().__init__()
        self.ps1 = ps1

    def __repr__(self) -> str:
        return f"{type(self).__name__}(ps1={self.ps1})"

    def input(self, prompt: str | None = None) -> str:
        if prompt is None:
            prompt = self.ps1
        return input(prompt)


class MultipleInputStrategy(InputStrategy):
    """Represents the method to get a user input per prompt
    in interactive mode.

    It consumes multiple lines and reduce them to a string,
    and users must confirm their input by sending EOF (^D)."""

    def __init__(self, ps1: str = "", ps2: str = "") -> None:
        super().__init__()
        self.ps1 = ps1

        if ps1 != "" and ps2 == "":
            # try to have the same value with ps1
            self.ps2 = self.ps1
        else:
            self.ps2 = ps2

    def __repr__(self) -> str:
        return f"{type(self).__name__}(ps1={self.ps1}, ps2={self.ps2})"

    def input(self, prompt: str | None = None) -> str:
        buffer = []
        _prompt = None
        if prompt is not None:
            self.ps1 = prompt
            self.ps2 = prompt
        else:
            _prompt = self.ps1

        while True:
            try:
                line = input(_prompt)
                buffer.append(line)
                _prompt = self.ps2
            except EOFError:
                if buffer:
                    sys.stdout.write("\n")
                    break
                else:
                    raise

        return "".join(buffer)