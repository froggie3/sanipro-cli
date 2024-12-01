import argparse
import logging
import pprint
from collections.abc import Sequence

from sanipro import pipeline
from sanipro.compatible import Self
from sanipro.parser import TokenInteractive, TokenNonInteractive
from sanipro.utils import HasPrettyRepr

from saniprocli import inputs
from saniprocli.abc import CommandsInterface, RunnerInterface
from saniprocli.cli_runner import RunnerInteractive, RunnerNonInteractive

from .color import style_for_readline
from .help_formatter import SaniproHelpFormatter
from .logger import get_log_level_from, logger_fp

logger_root = logging.getLogger()

logger = logging.getLogger(__name__)


class CommandsBase(HasPrettyRepr, CommandsInterface):
    input_delimiter = ","
    interactive = False
    one_line = False
    output_delimiter = ", "
    ps1 = f">>> "
    ps2 = f"... "

    filter: str | None = None
    verbose: int | None = None

    def get_logger_level(self) -> int:
        if self.verbose is None:
            return logging.WARNING
        try:
            log_level = get_log_level_from(self.verbose)
            return log_level
        except ValueError:
            raise ValueError("the maximum two -v flags can only be added")

    def to_runner(self) -> RunnerInterface:
        """The factory method for Runner class.
        Instantiated instance will be switched by the command option."""

        pipeline = self.get_pipeline()
        runner = None

        ps1 = style_for_readline(self.ps1)
        ps2 = style_for_readline(self.ps2)

        strategy = (
            inputs.OnelineInputStrategy(ps1)
            if self.one_line
            else inputs.MultipleInputStrategy(ps1, ps2)
        )
        runner = (
            RunnerInteractive(pipeline, TokenInteractive, strategy)
            if self.interactive
            else RunnerNonInteractive(pipeline, TokenNonInteractive, strategy)
        )

        return runner

    def get_pipeline(self) -> pipeline.PromptPipeline:
        """Gets user-defined pipeline."""
        ...

    def debug(self) -> None:
        """Shows debug message"""
        pprint.pprint(self, logger_fp)

    @classmethod
    def prepare_parser(cls) -> argparse.ArgumentParser:
        """Prepares argument parser."""
        parser = argparse.ArgumentParser(
            prog="sanipro",
            description=(
                "Toolbox for Stable Diffusion prompts. "
                "'Sanipro' stands for 'pro'mpt 'sani'tizer."
            ),
            formatter_class=SaniproHelpFormatter,
            epilog="Help for each filter is available, respectively.",
        )

        parser.add_argument(
            "-v",
            "--verbose",
            action="count",
            help=(
                "Switch to display the extra logs for nerds, "
                "This may be useful for debugging."
                "Adding more flags causes your terminal more messier."
            ),
        )

        parser.add_argument(
            "-d",
            "--input-delimiter",
            type=str,
            default=cls.input_delimiter,
            help=("Preferred delimiter string for the original prompts. " ""),
        )

        parser.add_argument(
            "-s",
            "--output-delimiter",
            default=cls.output_delimiter,
            type=str,
            help=("Preferred delimiter string for the processed prompts. " ""),
        )

        parser.add_argument(
            "-p",
            "--ps1",
            default=cls.ps1,
            type=str,
            help=(
                "The custom string that is used to wait for the user input "
                "of the prompts."
            ),
        )

        parser.add_argument(
            "--ps2",
            default=cls.ps2,
            type=str,
            help=(
                "The custom string that is used to wait for the next user "
                "input of the prompts."
            ),
        )

        parser.add_argument(
            "-i",
            "--interactive",
            default=cls.interactive,
            action="store_true",
            help=(
                "Provides the REPL interface to play with prompts. "
                "The program behaves like the Python interpreter."
            ),
        )

        parser.add_argument(
            "-l",
            "--one-line",
            default=cls.one_line,
            action="store_true",
            help=("Whether to confirm the prompt input with a single line of input."),
        )

        # This creates the global parser.
        cls.append_parser(parser)

        # This creates the user-defined subparser.
        cls.append_subparser(parser)

        return parser

    @classmethod
    def append_parser(cls, parser: argparse.ArgumentParser) -> None: ...

    @classmethod
    def append_subparser(cls, parser: argparse.ArgumentParser) -> None: ...

    @classmethod
    def from_sys_argv(cls, arg_val: Sequence) -> Self:
        parser = cls.prepare_parser()
        args = parser.parse_args(arg_val, namespace=cls())

        return args
