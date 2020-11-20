#!/usr/bin/env python3.8

from typing import Tuple, List, Any, Optional, TypeVar, Iterable, Callable, Dict, Set
from dataclasses import dataclass, fields

from subprocess import Popen, PIPE
from datetime import datetime
from time import sleep
from random import shuffle

import json
import csv
import sys

from ZoomCommanderLib import *


### CONFIG


max_num_students_in_breakout_rooms = 1


### GENERAL HELPERS

T = TypeVar("T")


def find(elems: Iterable[T], pred: Callable[[T], bool]) -> Optional[T]:
    return next((e for e in elems if pred(e)), None)


def format_time(t: datetime) -> str:
    return str(t)  # default format


### DATA STRUCTURES


@dataclass
class BreakoutRoomData:
    room_name: str
    participants: List[str]

    @property
    def occupation(self) -> int:
        return len(self.participants)

    @property
    def student_occupation(self) -> int:
        return self.occupation - len(self.assistants())

    def is_empty(self) -> bool:
        return self.occupation == 0

    def assistants(self) -> List[str]:
        return list(filter(is_assistant, self.participants))

    def has_assistant(self) -> bool:
        return any(is_assistant(p) for p in self.participants)


needed_field_names = [field.name for field in fields(BreakoutRoomData)]


@dataclass
class StateDiff:
    left: Set[str]
    new_unassigned: Set[str]


@dataclass
class CallState:
    room_data: List[BreakoutRoomData]
    unassigned_room: Optional[BreakoutRoomData]

    @property
    def unassigned_participants(self) -> Set[str]:
        if r := self.unassigned_room:
            return set(r.participants)
        else:
            return set()

    @property
    def all_participants(self) -> Set[str]:
        participants = set(self.unassigned_participants)
        for r in self.room_data:
            for p in r.participants:
                participants.add(p)
        return participants

    def dump(self):
        def print_participants(ps: List[str]):
            for p in sorted(ps, key=lambda p: (not is_assistant(p), p)):
                prefix = " * " if is_assistant(p) else "   "
                print(prefix + p)

        for room in self.room_data:
            print(room.room_name + ":", end="")
            if room.is_empty():
                print(" -")
            else:
                print()
                print_participants(room.participants)
        unassigned = self.unassigned_participants
        if len(unassigned) == 0:
            print("Unassigned: -")
        else:
            print("Unassigned:")
            print_participants(unassigned)

    def room_for_new_assistant(self, exclude: Set[str]) -> Optional[BreakoutRoomData]:
        rooms_no_assistant = filter(lambda r: not r.has_assistant() and r.room_name not in exclude, self.room_data)
        sorted_rooms = sorted(rooms_no_assistant, key=lambda r: -r.occupation)
        if len(sorted_rooms) == 0:
            return None
        else:
            return sorted_rooms[0]

    def openings(self) -> List[BreakoutRoomData]:
        candidate_rooms = list(filter(
            lambda r: r.has_assistant()
            and r.student_occupation < max_num_students_in_breakout_rooms,
            self.room_data,
        ))
        # suffling before sorted ensures a random order within the same occupation value
        shuffle(candidate_rooms)
        return sorted(candidate_rooms, key=lambda r: r.student_occupation)

    def compare_to_new(self, new: "CallState") -> StateDiff:
        old = self
        left = old.all_participants.difference(new.all_participants)
        new_unassigned = set(new.unassigned_participants).difference(
            old.unassigned_participants
        )
        return StateDiff(left, new_unassigned)



@dataclass
class ParticipantTimes:
    join_time: datetime
    assignment: Optional[Assignment] = None
    kicked: bool = False

    def __repr__(self) -> str:
        join_data = format_time(self.join_time)
        assignment_data = (
            ""
            if not self.assignment
            else f", -> {self.assignment.assistant} ({format_time(self.assignment.time)})"
        )
        return f"{join_data}{assignment_data}"


### APPLESCRIPT/ZOOM COMMUNICATION

with open("ZoomScript.applescript", encoding="utf-8") as f:
    applescript_prelude = f.read()


def run_applescript(script: str) -> Optional[Any]:
    with Popen(
        ["osascript", "-e", f"{applescript_prelude}return toJson({script})"],
        stdout=PIPE,
        stderr=PIPE,
        universal_newlines=False,
    ) as p:
        stdoutb, stderrb = p.communicate()
    stdout = stdoutb.decode("utf-8")
    stderr = stderrb.decode("utf-8")
    if p.returncode != 0:
        print(f"Cannot run script '{script}', return code = {p.returncode}")
        print(f"{stdout=}")
        print(f"{stderr=}")
        return None
    return json.loads(stdout)


### APPLESCRIPT WRAPPERS


def get_state() -> Optional[CallState]:
    json_data = run_applescript(r"""getBreakoutRooms()""")
    if not json_data:
        return None
    room_data: List[BreakoutRoomData] = []
    unassigned_room: Optional[BreakoutRoomData] = None
    for room_data_dict in json_data:
        data_complete = True
        for field_name in needed_field_names:
            if field_name not in room_data_dict:
                print(f"missing field '{field_name}' in dict {room_data_dict}")
                data_complete = False
        if data_complete:
            room = BreakoutRoomData(**room_data_dict)
            if room.room_name == "Unassigned":
                unassigned_room = room
            else:
                room_data.append(room)
    return CallState(room_data, unassigned_room)


def assign(participant: str, room_name: str) -> None:
    print(f"Assigning '{participant}' to room '{room_name}'")
    if out := run_applescript(f"""assignToRoom("{room_name}", "{participant}")"""):
        print(f" > {out}")
    

def broadcast(message: str) -> None:
    print(f"Broadcasting '{message}'")
    run_applescript(f"""broadcastMessage("{message}")""")

def send_to_main_room(message: str) -> None:
    print(f"Sending to main room '{message}'")
    run_applescript(f"""sendInMainRoom("{message}")""")



def parse_command(name: str) -> Optional[Tuple[str,str]]:
    start_str, col_str, end_str = "{{", ":", "}}"
    start = name.find(start_str)
    if start == -1:
        return None
    end = name.find(end_str, start)
    if end == -1:
        return None
    full_cmd = name[start + len(start_str):end]
    col = full_cmd.find(col_str)
    if col == -1:
        return None
    return full_cmd[:col].strip().lower(), full_cmd[col + 1:].strip()


### MAIN LOOP

join_time: Dict[str, ParticipantTimes] = {}

# Could be done better with finally?
class GoodbyeSayer:
    def __enter__(self) -> 'GoodbyeSayer':
        return self
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        print("Files flushed, exiting")


with open("timings.csv", mode="a", encoding="utf-8") as timings_file, open(
    "state.csv", mode="a", encoding="utf-8"
) as state_file, GoodbyeSayer() as _:

    # Prepare log files and handlers

    session_header = f"-- Session started at {format_time(datetime.now())}"

    timings_writer = csv.writer(timings_file)
    timings_writer.writerow([session_header])
    timings_writer.writerow(["Name", "Joined", "Assigned", "TA", "Left"])

    def record_disconnect(
        name: str, times: ParticipantTimes, end_time: datetime
    ) -> None:
        assignment_data = (
            [format_time(times.assignment.time), times.assignment.assistant]
            if times.assignment
            else ["-", "-"]
        )
        row_data = [
            name,
            format_time(times.join_time),
            *assignment_data,
            format_time(end_time),
        ]
        timings_writer.writerow(row_data)
        print(f"{name:<15} {times.join_time} {' '.join(assignment_data)} {end_time}")
        timings_file.flush()

    state_writer = csv.writer(state_file)
    state_writer.writerow([session_header])
    state_writer.writerow(["Time", "Unassigned", "In Rooms"])

    def record_state(
        now: datetime, num_unassigned: int, num_in_rooms: List[int]
    ) -> None:
        row_data = [format_time(now), num_unassigned, *num_in_rooms]
        state_writer.writerow(row_data)
        state_file.flush()

    initial_state = get_state()
    if not initial_state:
        print("Cannot get initial state, stopping")
        sys.exit(1)
    else:
        old_state = initial_state

    last_published_priority_list: List[str] = []
    last_published_queue_length = 0

    # Main polling loop

    while True:
        sleep(2.0)
        now = datetime.now()
        new_state = get_state()
        if not new_state:
            print("Cannot get new state, skipping this turn")
            continue

        record_state(
            now,
            num_unassigned=len(new_state.unassigned_participants),
            num_in_rooms=list(
                filter(
                    lambda n: n > 0,
                    map(lambda r: len(r.participants), new_state.room_data),
                )
            ),
        )
        diff = old_state.compare_to_new(new_state)
        print("old:")
        old_state.dump()
        print("--")
        print("new:")
        new_state.dump()
        print("--")
        print("join times:")
        for name, time in join_time.items():
            print(f"  {name:15} -> {time}")
        print("--")

        # Record those who disconnected
        for left in diff.left:
            print(f" -> Cleared: {left}")
            if left in join_time:
                record_disconnect(left, join_time[left], now)
                del join_time[left]

        num_just_assigned = 0
        assigned_to_assistant: Set[str] = set()
        for unassigned in new_state.unassigned_participants:
            if unassigned not in join_time:
                join_time[unassigned] = ParticipantTimes(now)
            if is_assistant(unassigned):
                if r := new_state.room_for_new_assistant(exclude=assigned_to_assistant):
                    assign(participant=unassigned, room_name=r.room_name)
                    assigned_to_assistant.add(r.room_name)
                    num_just_assigned += 1
            
        students_to_assign: List[str] = list(
            filter(lambda p: not is_assistant(p), new_state.unassigned_participants)
        )
        priority_list = sorted(students_to_assign, key=lambda p: join_time[p].join_time)
        if priority_list != last_published_priority_list:
            last_published_priority_list = priority_list
            if not priority_list:
                queue_str = "(vide)"
            else:
                def queue_line(name: str, position: int) -> str:
                    wait_dur_sec = (now - join_time[name].join_time).total_seconds()
                    if wait_dur_sec < 60:
                        wait_dur = "moins d'une min"
                    elif wait_dur_sec < 100: # round a bit
                        wait_dur = "env. une min"
                    else:
                        num_min = (wait_dur_sec + 30) // 60
                        wait_dur = f"env. {num_min} min"
                    return f"{position:>3}. {name} – depuis {wait_dur}"

                queue_str = "\n" + "\n".join(queue_line(name, i+1) for i, name in enumerate(priority_list)) + "\n----"
            time_str = now.strftime("%Hh%M")
            send_to_main_room(f"Liste d’attente à {time_str}: {queue_str}")

        if len(students_to_assign) == 0:
            print("No student left to assign")
        else:
            print("Free rooms for students: ", end="")
            openings = new_state.openings()
            if len(openings) == 0:
                print("-")
            else:
                print()
                for opening in openings:
                    assistants = opening.assistants()
                    assistants_str = "; ".join(assistants)
                    print(f"  - {opening.room_name} ({assistants_str} + {len(opening.participants) - len(assistants)} students)")
                for r, participant in zip(openings, priority_list):
                    assign(participant, r.room_name)
                    num_just_assigned += 1
                    join_time[participant].assignment = Assignment(
                        now, r.assistants()[0]
                    )

        queue_length = len(new_state.unassigned_participants) - num_just_assigned
        if (queue_diff := queue_length - last_published_queue_length) != 0:
            diff_str = str(queue_diff) if queue_diff < 0 else f"+{queue_diff}"
            last_published_queue_length = queue_length
            broadcast(f"Maintenant en attente: {queue_length} (Δ = {diff_str})")

        # Process commands
        for room in new_state.room_data:
            for name in room.participants:
                if full_cmd := parse_command(name):
                    cmd, arg = full_cmd
                    if cmd == "kick" and len(arg) > 0:
                        user_name_start_pattern = arg.lower()
                        if is_assistant(name):
                            if target := next((n for n in room.participants if n.strip().lower().startswith(user_name_start_pattern)), None):
                                print(f"Moving aside '{target}' upon request from '{name}'")
                                join_time[target].kicked = True
                                assign(target, new_state.room_data[-1].room_name)
                            else:
                                print(f"No target found to honor command '{cmd}' with arg '{arg}'")
                    else:
                        print(f"Unknown command: {full_cmd}")

        print(now)
        print("-----------------")
        old_state = new_state

