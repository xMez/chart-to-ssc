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


SSC_HEADER_SOULLESS_5 = """#VERSION:0.83;
#TITLE:Soulless 5;
#SUBTITLE:;
#ARTIST:ExileLord;
#TITLETRANSLIT:;
#SUBTITLETRANSLIT:;
#ARTISTTRANSLIT:;
#GENRE:;
#CREDIT:;
#MUSIC:song.ogg;
#BANNER:;
#BACKGROUND:;
#CDTITLE:;
#SAMPLESTART:0.000;
#SAMPLELENGTH:0.000;
#SELECTABLE:YES;
#OFFSET:0.010;
#BPMS:0.000=130.000;
#STOPS:;
#BGCHANGES:;
#FGCHANGES:;
//--------------- pump-single - Mez ----------------
#NOTEDATA:;
#STEPSTYPE:pump-single;
#DESCRIPTION:Mez;
#DIFFICULTY:Challenge;
#METER:30;
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


if __name__ == "__main__":
    with open("notes.chart", encoding="utf-8") as file:
        while line := file.readline().strip():
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

    with open("[ExpertSingle]2.ssc", "w", encoding="utf-8") as file:
        taps = starts = ends = 0
        start_tick = min(NOTE_QUEUES["[ExpertSingle]"].keys())
        end_tick = max(NOTE_QUEUES["[ExpertSingle]"].keys())
        logging.info(f"Generating from {start_tick} to {end_tick} for a total of {end_tick - start_tick}")
        logging.debug(f"Start note: {NOTE_QUEUES['[ExpertSingle]'][start_tick]}")
        logging.debug(f"End note: {NOTE_QUEUES['[ExpertSingle]'][end_tick]}")
        file.write(SSC_HEADER_SOULLESS_5)
        for tick in range(0, end_tick + 1):
            line = [0] * 5
            for note in NOTE_QUEUES["[ExpertSingle]"].get(tick, []):
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
        logging.info(f"Generated chart with {taps} taps, {starts} starts, {ends} ends")
        file.write(";\n")
