import argparse
import collections
import collections.abc
import os
import re
import readline
import sys
import typing

from sanipro.compatible import Self
from sanipro.delimiter import Delimiter
from sanipro.logger import logger, logger_root
from sanipro.token import Escaper

from saniprocli import inputs
from saniprocli.abc import CliRunnable, InputStrategy
from saniprocli.cli_runner import ExecuteSingle, RunnerDeclarative, RunnerInteractive
from saniprocli.commands import (
    CliArgsNamespaceDefault,
    CliCommands,
    SubparserInjectable,
)
from saniprocli.help_formatter import SaniproHelpFormatter
from saniprocli.sanipro_argparse import SaniproArgumentParser
from saniprocli.textutils import CSVUtilsBase, dump_to_file, get_temp_filename


class CliArgsNamespaceDemo(CliArgsNamespaceDefault):
    # global options
    interactive: bool

    input_delimiter: str
    output_delimiter: str
    output_field_separator: str

    formatter: str

    # 'dest' name for general operations
    operation_id = str  # may be 'filter', 'set_op', and more

    # for tfind subcommand
    infile: typing.TextIO
    key_field: int
    value_field: int
    dict_field_separator: str
    tempdir: str

    clipboard: bool
    config: str

    def is_tfind(self) -> bool:
        return self.operation_id == CliSubcommandSearchTag.command_id

    @classmethod
    def _do_append_parser(cls, parser: SaniproArgumentParser) -> None:
        parser.add_argument(
            "-d",
            "--input-delimiter",
            type=str,
            default="\n",
            help=("Preferred delimiter for input."),
        )

        parser.add_argument(
            "-D",
            "--output-delimiter",
            default="\n",
            type=str,
            help=("Preferred delimiter for output."),
        )

        parser.add_argument(
            "-f",
            "--dict-field-separator",
            default=",",
            type=str,
            help=("Preferred field separator for dict file."),
        )

        parser.add_argument(
            "-F",
            "--output-field-separator",
            default=",",
            type=str,
            help=("Preferred output field separator for output."),
        )

        parser.add_argument(
            "--formatter",
            default="csv",
            choices=Formatter.choices,
            type=str,
            help=("Preferred format for output."),
        )

    @classmethod
    def _do_append_subparser(cls, parser: SaniproArgumentParser) -> None:
        subparser = parser.add_subparsers(
            title="operations", dest="operation_id", required=True
        )

        classes: list[type[SubparserInjectable]] = [CliSubcommandSearchTag]

        for cmd in classes:
            cmd.inject_subparser(subparser)


class CsvUtils(CSVUtilsBase):
    def _do_preprocess(self, column: list[str]):
        column[0] = self.replace_underscore(column[0])
        return column

    def replace_underscore(self, line: str) -> str:
        line = line.strip()
        line = line.replace("_", " ")
        return line


class TFindEscaper:
    parentheses = re.compile(r"([\(\)])")

    @staticmethod
    def escape_parentheses(text: str):
        """Escapes a backslash which possibly allows another backslash
        comes after it.

        e.g. `( ) ===> \\( \\)`"""

        return re.sub(TFindEscaper.parentheses, r"\\\g<1>", text)


class Formatter:
    choices = ["a1111", "a1111compat", "csv"]

    @staticmethod
    def to_csv(token: str) -> str:
        return token

    @staticmethod
    def to_a1111(token: str) -> str:
        return TFindEscaper.escape_parentheses(token)

    @staticmethod
    def to_a1111_compat(token: str) -> str:
        token = TFindEscaper.escape_parentheses(token)
        return Escaper.escape(token)


class WeightedFormatter:
    choices = ["csv"]

    @staticmethod
    def to_csv(delimiter: str) -> collections.abc.Callable:
        def f(token: str) -> str:
            return "%s%s%f" % (token, delimiter, 1.0)

        return f


class TokenFinder:
    def __init__(self, delimiter: Delimiter, formatter: collections.abc.Callable):
        self._delimiter = delimiter
        self._formatter = formatter

    def execute(self, prompt: str, kvstore: dict[str, str]) -> str:
        in_d = self._delimiter.sep_input
        out_d = self._delimiter.sep_output
        field_d = self._delimiter.sep_field

        if field_d is None:
            raise ValueError("field delimiter is None")

        result = []

        for token in prompt.split(in_d):
            new_token = token.strip()
            if not new_token:
                break

            nums = kvstore.get(new_token, "NULL")
            token_escaped = self._formatter(new_token)
            columns = [token_escaped, nums]

            serialized = field_d.join(columns)
            result.append(serialized)

        return out_d.join(result)


class RunnerTagFindInteractive(ExecuteSingle, RunnerInteractive):
    """Represents the runner specialized for the filtering mode."""

    _histfile: str

    def __init__(
        self,
        finder: TokenFinder,
        tags_n_count: dict[str, str],
        strategy: InputStrategy,
        tempdir: str,
        use_clipboard: bool,
    ) -> None:
        self._app = finder
        self._input_strategy = strategy
        self.tags_n_count: dict[str, str] = tags_n_count
        self.tempdir = tempdir
        self._use_clipboard = use_clipboard

    @classmethod
    def create_from_csv(
        cls,
        finder: TokenFinder,
        text: typing.TextIO,
        strategy: InputStrategy,
        delim: str,
        key_idx: int,
        value_idx: int,
        tempdir: str,
        use_clipboard: bool,
    ) -> Self:
        """Import the key-value storage from a comma-separated file.
        The index starts from 1. This is because common traditional command-line
        utilities assume the field index originates from 1.

        The `tempdir` is used to store the history file for the GNU Readline.
        """

        try:
            tag_n_count = CsvUtils.create_dict_from_io(text, delim, key_idx, value_idx)
            return cls(finder, tag_n_count, strategy, tempdir, use_clipboard)
        except IndexError as e:
            raise type(e)

    def _on_init(self) -> None:
        histfile = get_temp_filename(self.tempdir)
        dump_to_file(histfile, self.tags_n_count.keys())

        try:
            readline.read_history_file(histfile)
        except FileNotFoundError as e:
            raise type(e)("failed to read history file: %s" % (histfile,))

        # so that the file is deleted after the program exits
        self._histfile = histfile

    def _on_exit(self) -> None:
        try:
            os.remove(self._histfile)
        except OSError:
            logger.warning("%s: history file was not deleted", self._histfile)

    def _execute_single_inner(self, source: str) -> str:
        return self._app.execute(source, self.tags_n_count)


class RunnerTagFindNonInteractive(ExecuteSingle, RunnerDeclarative):
    """Represents the runner specialized for the filtering mode."""

    def __init__(
        self, finder: TokenFinder, tags_n_count: dict[str, str], strategy: InputStrategy
    ) -> None:
        self._app = finder
        self._input_strategy = strategy
        self.tags_n_count: dict[str, str] = tags_n_count
        self._histfile = ""

    @classmethod
    def create_from_csv(
        cls,
        finder: TokenFinder,
        text: typing.TextIO,
        strategy: InputStrategy,
        delim: str,
        key_idx: int,
        value_idx: int,
    ) -> Self:
        """Import the key-value storage from a comma-separated file.
        The index starts from 1. This is because common traditional command-line
        utilities assume the field index originates from 1."""
        try:
            tags_n_count = CsvUtils.create_dict_from_io(text, delim, key_idx, value_idx)
            return cls(finder, tags_n_count, strategy)
        except IndexError:
            raise

    def _execute_single_inner(self, source: str) -> str:
        return self._app.execute(source, self.tags_n_count)


class CliCommandsDemo(CliCommands):
    def __init__(self, args: CliArgsNamespaceDemo) -> None:
        self._args = args

    def _get_input_strategy(self) -> InputStrategy:
        if not self._args.interactive:
            return inputs.DirectInputStrategy()

        ps1 = self._args.ps1
        ps2 = self._args.ps2

        return (
            inputs.OnelineInputStrategy(ps1)
            if self._args.one_line
            else inputs.MultipleInputStrategy(ps1, ps2)
        )

    def to_runner(self) -> CliRunnable:
        delimiter = Delimiter(
            self._args.input_delimiter,
            self._args.output_delimiter,
            self._args.output_field_separator,
        )

        input_strategy = self._get_input_strategy()

        fmt_mapping = {
            "a1111compat": Formatter.to_a1111_compat,
            "a1111": Formatter.to_a1111,
            "csv": Formatter.to_csv,
        }

        formatter = None
        try:
            formatter = fmt_mapping[self._args.formatter]
        except KeyError as e:
            raise type(e)("no formatter applicable: %s", self._args.formatter)

        finder = TokenFinder(delimiter, formatter)

        if self._args.is_tfind():
            if self._args.interactive:
                return RunnerTagFindInteractive.create_from_csv(
                    finder,
                    self._args.infile,
                    input_strategy,
                    self._args.dict_field_separator,
                    self._args.key_field,
                    self._args.value_field,
                    self._args.tempdir,
                    self._args.clipboard,
                )

            return RunnerTagFindNonInteractive.create_from_csv(
                finder,
                self._args.infile,
                input_strategy,
                self._args.dict_field_separator,
                self._args.key_field,
                self._args.value_field,
            )
        else:  # default
            raise NotImplementedError


class CliSubcommandSearchTag(SubparserInjectable):
    command_id: str = "tfind"

    @classmethod
    def inject_subparser(cls, subparser: argparse._SubParsersAction) -> None:
        parser = subparser.add_parser(
            name=cls.command_id,
            formatter_class=SaniproHelpFormatter,
            help=("Outputs the number of posts corresponds the tag specified."),
            description=(
                "In this mode a user specifies a CSV file acting as a key-value storage. "
                "The first which is the `key` column corresponds to the name of the tag, "
                "so do second which is the `value` column to the count of the assigned tag."
            ),
        )

        parser.add_argument(
            "infile",
            type=argparse.FileType("r"),
            help=(
                "Specifies the text file comprised from two columns, "
                "each separated with delimiter."
            ),
        )

        parser.add_argument(
            "-i",
            "--interactive",
            default=False,
            action="store_true",
            help=(
                "Provides the REPL interface to play with prompts. "
                "The program behaves like the Python interpreter."
            ),
        )

        parser.add_argument(
            "-k",
            "--key-field",
            default=1,
            type=int,
            help="Select this field number's element as a key.",
        )

        parser.add_argument(
            "-v",
            "--value-field",
            default=2,
            type=int,
            help="Select this field number's element as a value.",
        )

        parser.add_argument(
            "-t",
            "--tempdir",
            default="/dev/shm",
            type=str,
            help=(
                "Use this directory as a tempfile storage. Technically speaking, "
                "the program creates a new text file by extracting the field "
                "from a csv file, format and save them so the GNU Readline "
                "can read the histfile on this directory."
            ),
        )

        parser.add_argument(
            "-c",
            "--clipboard",
            default=False,
            action="store_true",
            help="Copy the result to the clipboard if possible.",
        )


def app():
    args = CliArgsNamespaceDemo.from_sys_argv(sys.argv[1:])
    cli_commands = CliCommandsDemo(args)

    log_level = cli_commands.get_logger_level()
    logger_root.setLevel(log_level)

    try:
        runner = cli_commands.to_runner()
    except AttributeError as e:
        logger.error(f"error: {e}")
        exit(1)

    runner.run()


if __name__ == "__main__":
    app()