import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal, TextIO

logging.basicConfig(level=logging.DEBUG)


@dataclass
class Note:
    tick: int
    pos: int
    ntype: Literal["Tap", "Start", "End"]


class ParsingError(Exception):
    pass


METADATA = {}
SSC_HEADER_TEMPLATE = """#VERSION:0.83;
#TITLE:{Name};
#SUBTITLE:;
#ARTIST:{Artist};
#TITLETRANSLIT:;
#SUBTITLETRANSLIT:;
#ARTISTTRANSLIT:;
#GENRE:{Genre};
#CREDIT:;
#MUSIC:song.ogg;
#BANNER:;
#BACKGROUND:;
#CDTITLE:{Album};
#SAMPLESTART:0.000;
#SAMPLELENGTH:0.000;
#SELECTABLE:YES;
#OFFSET:{Offset};
#BPMS:{Bpms};
#STOPS:;
#SPEEDS:0.000=1.000=0.000=0;
#SCROLLS:0.000=1.000;
#TICKCOUNTS:0.000=4;
#BGCHANGES:;
#FGCHANGES:;
"""
DIFF_HEADER_TEMPLATE = """
//--------------- pump-single - Converted ----------------
#NOTEDATA:;
#STEPSTYPE:pump-single;
#DESCRIPTION:Converted;
#DIFFICULTY:Challenge;
#METER:{level};
#RADARVALUES:0,0,0,0,0;
#NOTES:
"""
PARSING = ""
CURRENT_TICK = -1
NOTE_QUEUES: dict[str, dict[int, list[Note]]] = {
    "[ExpertSingle]": defaultdict(list),
    "[HardSingle]": defaultdict(list),
    "[MediumSingle]": defaultdict(list),
    "[EasySingle]": defaultdict(list),
}


def generate_notes(line: str) -> None:
    tick_str, sep, note_str = line.partition(" = N ")
    if sep:
        tick = int(tick_str) // 4
        note_data = note_str.split(" ")
        if note_data[0] in "567":
            return
        note = Note(tick=tick, pos=int(note_data[0]), ntype="Tap" if note_data[1] == "0" else "Start")
        NOTE_QUEUES[PARSING][note.tick].append(note)
        if note.ntype == "Start":
            note = Note(
                tick=note.tick + int(note_data[1]) // 4,
                pos=note.pos,
                ntype="End",
            )
            NOTE_QUEUES[PARSING][note.tick].append(note)
def parse_metadata(file: TextIO) -> None:
    file.readline()  # Skip line
    while (line := file.readline().strip()) != "}":
        key, _, value = line.partition(" = ")
        METADATA[key] = value.strip('"')
    if METADATA["Resolution"] != "192":
        msg = "Unsupported resolution, only 192 supported"
        raise ParsingError(msg)
    logging.info(f"Parsed metadata: {METADATA}")


def parse_bpm(file: TextIO) -> None:
    file.readline()  # Skip line
    bpms: list[str] = []
    while (line := file.readline().strip()) != "}":
        tick_str, _, sync_str = line.partition(" = ")
        if "TS" in sync_str:
            if sync_str != "TS 4":
                msg = "Unsupported time signature, only 4/4 supported"
                raise ParsingError(msg)
            continue
        bpm = sync_str.split(" ")[1]
        bpms.append(f"{tick_str}.000={bpm[:3]}.{bpm[3:]}")
    METADATA["Bpms"] = ",".join(bpms)
    logging.info(f"Parsed bpms: {bpms}")


def generate_difficulty(file: TextIO, level: int, diff: str) -> None:
    start_tick = min(NOTE_QUEUES[diff].keys())
    end_tick = max(NOTE_QUEUES[diff].keys())
    logging.info(f"Generating {diff} from {start_tick} to {end_tick} for a total of {end_tick - start_tick} ticks")
    logging.debug(f"Start note: {NOTE_QUEUES[diff][start_tick]}")
    logging.debug(f"End note: {NOTE_QUEUES[diff][end_tick]}")
    taps = starts = ends = 0
    for tick in range(0, end_tick + 1):
        line = [0] * 5
        for note in NOTE_QUEUES[diff].get(tick, []):
            match note.ntype:
                case "Tap":
                    line[note.pos] = 1
                    taps += 1
                case "Start":
                    line[note.pos] = 2
                    starts += 1
                case "End":
                    line[note.pos] = 3
                    ends += 1
        file.write("".join(map(str, line)) + "\n")
        if tick != 0 and tick != end_tick and (tick + 1) % 192 == 0:
            file.write(",\n")
    logging.info(f"Generated {diff} with {taps} taps, {starts} starts, {ends} ends")
    file.write(";\n")


if __name__ == "__main__":
    with open("notes.chart", encoding="utf-8") as file:
        while line := file.readline().strip():
            if line == "[Song]":
                parse_metadata(file)
            if line == "[SyncTrack]":
                parse_bpm(file)
            if line in NOTE_QUEUES.keys():
                logging.info(f"Found difficulty: {line}")
                PARSING = line
                file.readline()  # Skip line
                continue
            if not PARSING:
                continue
            if line == "}":
                PARSING = ""
                continue

            generate_notes(line)

    logging.info("Done loading!")

    with open("audio.ssc", "w", encoding="utf-8") as file:
        file.write(SSC_HEADER_TEMPLATE.format(**METADATA))
        for level, diff in enumerate(NOTE_QUEUES):
            generate_difficulty(file, 30 - level * 3, diff)
