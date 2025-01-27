from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable

from sanipro.logger import logger


class CSVUtilsBase(ABC):
    def __init__(self, lines: list[str], delim: str) -> None:
        self.lines = lines
        self.delim = delim

    @classmethod
    def is_ranged_or_raise(cls, key_idx: int, value_idx: int) -> None:
        if key_idx < 1 or value_idx < 1:
            raise ValueError("field number must be 1 or more")

    @classmethod
    def is_different_idx_or_raise(cls, key_idx: int, value_idx: int) -> None:
        if key_idx == value_idx:
            raise ValueError("impossible to specify the same field number")

    def preprocess(self, lines: list[str]) -> Generator[list[str], None, None]:
        for line in lines:
            line = line.strip()
            columns = line.split(self.delim)
            processed = self._do_preprocess(columns)
            yield processed

    @abstractmethod
    def _do_preprocess(self, column: list[str]) -> list[str]:
        raise NotImplementedError

    def prepare_kv(self, key_idx: int, value_idx: int):
        self.is_ranged_or_raise(key_idx, value_idx)
        self.is_different_idx_or_raise(key_idx, value_idx)
        lines = self.lines

        k = key_idx - 1
        v = value_idx - 1

        try:
            it = self.preprocess(lines)
            return {row[k]: row[v] for row in it}
        except IndexError as e:
            raise type(e)("failed to get the element of the row number")

    @classmethod
    def create_dict_from_io(cls, *args) -> dict[str, str]:
        """A helper function for creating the dictionary from the CSV file."""

        text, *rest, key_idx, value_idx = args

        # NOTE: meaning dict file is always delimited by line breaks. is it good thing?
        lines = text
        return cls(lines, *rest).prepare_kv(key_idx, value_idx)


def get_temp_filename(tmp_dir: str) -> str:
    """Returns a temporary filename.
    The temporary file must be deleted after calling this function."""

    import tempfile

    _tmpfile = tempfile.NamedTemporaryFile(dir=tmp_dir, delete=False)
    filename = _tmpfile.name
    _tmpfile.close()
    return filename


def dump_to_file(path: str, lines: Iterable[str]) -> None:
    """Dump lines to file."""

    with open(path, mode="w") as fp:
        fp.write("\n".join(lines))
        fp.write("\n")


class ClipboardHandler:
    @staticmethod
    def copy_to_clipboard(text: str) -> None:
        """Copy the text to clipboard."""
        import pyperclip

        try:
            pyperclip.copy(text)
        except pyperclip.PyperclipException as e:
            logger.warning(e)
