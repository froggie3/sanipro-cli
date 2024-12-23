import logging
import sys
import time
from abc import ABC, abstractmethod

from sanipro.diff import PromptDifferenceDetector
from sanipro.pipeline import PromptPipeline
from sanipro.promptset import SetCalculatorWrapper

from saniprocli import cli_hooks, color
from saniprocli.abc import (
    CliPlural,
    CliRunnable,
    CliRunnableInnerRun,
    CliSingular,
    InputStrategy,
)

logger_root = logging.getLogger()

logger = logging.getLogger(__name__)


class RunnerInteractive(CliRunnable, CliRunnableInnerRun, ABC):
    """Represents the method for the program to interact
    with the users.

    This runner is used when the user decided to use
    the interactive mode.

    This is similar what Python interpreter does like."""

    @abstractmethod
    def _start_loop(self) -> None:
        """The actual start of the interaction with the user."""

    def _try_banner(self) -> None:
        """Tries to show the banner if possible,

        TODO implement an option whether to show the banner or not."""
        self._write(
            f"Sanipro (created by iigau) in interactive mode\n"
            f"Program was launched up at {time.asctime()}.\n"
        )

    def _on_init(self) -> None:
        """The method to be called before the actual interaction."""

    def _on_exit(self) -> None:
        """The method to be called after the actual interaction."""

    def run(self) -> None:
        cli_hooks.execute(cli_hooks.on_interactive)
        self._write = sys.stdout.write
        self._try_banner()
        self._on_init()
        self._start_loop()
        self._on_exit()


class RunnerInteractiveSingle(RunnerInteractive, CliSingular, ABC):
    """Represents the runner with the interactive user interface
    that expects a single input of the prompt."""

    def __init__(self, pipeline: PromptPipeline, strategy: InputStrategy) -> None:
        self._pipeline = pipeline
        self._token_cls = pipeline.token_cls
        self._input_strategy = strategy

        self._detector_cls = PromptDifferenceDetector

    @abstractmethod
    def _execute_single_inner(self, source: str) -> str:
        """Implements specific features that rely on inherited class."""

    def _execute_single(self, source: str) -> str:
        return self._execute_single_inner(source)

    def _start_loop(self) -> None:
        self._write = sys.stdout.write

        while True:
            try:
                try:
                    prompt_input = self._input_strategy.input()
                    if prompt_input:
                        out = self._execute_single(prompt_input)
                        self._write(f"{out}\n")
                except EOFError as e:
                    break
            except ValueError as e:  # like unclosed parentheses
                logger.fatal(f"error: {e}")
            except KeyboardInterrupt:
                self._write("\nKeyboardInterrupt\n")
        self._write(f"\n")


class RunnerInteractiveMultiple(RunnerInteractive, CliPlural, ABC):
    """Represents the runner with the interactive user interface
    that expects two different prompts."""

    def __init__(
        self,
        pipeline: PromptPipeline,
        strategy: InputStrategy,
        calculator: SetCalculatorWrapper,
    ) -> None:
        self._pipeline = pipeline
        self._token_cls = pipeline.token_cls
        self._input_strategy = strategy

        self._detector_cls = PromptDifferenceDetector
        self._calculator = calculator

    @abstractmethod
    def _execute_multi_inner(self, first: str, second: str) -> str:
        """Implements specific features that rely on inherited class."""

    def _execute_multi(self, first: str, second: str) -> str:
        return self._execute_multi_inner(first, second)

    def _handle_input(self) -> str:
        while True:
            try:
                prompt_input = self._input_strategy.input()
                if prompt_input:
                    return prompt_input
            except EOFError as e:
                raise EOFError("EOF received. Going back to previous state.")
            except KeyboardInterrupt:
                self._write("\nKeyboardInterrupt\n")
            except Exception as e:
                logger.fatal(f"error: {e}")

    def _start_loop(self) -> None:
        self._write = sys.stdout.write

        while True:
            try:
                state = 00
                first = ""
                second = ""
                _color = color.color_foreground

                while True:
                    if state == 00:
                        try:
                            first = self._handle_input()
                            if first:
                                state = 10
                        except EOFError:
                            raise
                    elif state == 10:
                        color.color_foreground = "green"
                        try:
                            second = self._handle_input()
                            if second:
                                state = 20
                        except EOFError:
                            state = 00  # reset state to 00
                            color.color_foreground = _color
                            continue
                    elif state == 20:
                        out = self._execute_multi(first, second)
                        self._write(f"{out}\n")
                        color.color_foreground = _color
                        break  # go to next set of prompts
            except EOFError:
                break
        self._write(f"\n")


class RunnerNonInteractiveSingle(CliRunnable, CliSingular, ABC):
    """Represents the method for the program to interact
    with the users in non-interactive mode.

    Intended the case where the users feed the input from STDIN.
    """

    def __init__(self, pipeline: PromptPipeline, strategy: InputStrategy) -> None:
        self._pipeline = pipeline
        self._token_cls = pipeline.token_cls
        self._input_strategy = strategy

    @abstractmethod
    def _execute_single_inner(self, source: str) -> str:
        """Implements specific features that rely on inherited class."""

    def _execute_single(self, source: str) -> str:
        return self._execute_single_inner(source)

    def _run_once(self) -> None:
        self._write = print
        sentence = ""
        try:
            sentence = self._input_strategy.input().strip()
        except (KeyboardInterrupt, EOFError):
            sys.stderr.write("\n")
            sys.exit(1)
        finally:
            out = self._execute_single(sentence)
            self._write(out)

    def run(self) -> None:
        self._run_once()
