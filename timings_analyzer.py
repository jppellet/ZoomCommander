from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Optional, List, Tuple
from ZoomCommanderLib import *
import csv


source_file = "timings/timings-2020-11-13.csv"



def format_duration(delta: timedelta) -> str:
    min, sec = divmod(int(delta.total_seconds()), 60)
    s = f"{sec} s" if min == 0 else f"{min} min {sec:0<2} s"
    return f"{s:>11}"



@dataclass
class Row:
    name: str
    join_time: datetime
    assignment: Optional[Assignment]
    disconnect_time: datetime

    @property
    def was_served(self) -> bool:
        return bool(self.assignment)

    @property
    def question_duration(self) -> timedelta:
        if not self.assignment:
            return timedelta(0)
        else:
            return self.disconnect_time - self.assignment.time

    @property
    def wait_duration(self) -> timedelta:
        if not self.assignment:
            return self.disconnect_time - self.join_time
        else:
            return self.assignment.time - self.join_time

    def __repr__(self) -> str:
        if not self.assignment:
            return f"{self.name:30} gave up after {format_duration(self.disconnect_time - self.join_time)}"
        else:
            return f"{self.name:30} waited {format_duration(self.assignment.time - self.join_time)}  and was helped  {format_duration(self.disconnect_time - self.assignment.time)} by {self.assignment.assistant}"


default_time_format = "%Y-%m-%d %H:%M:%S.%f"

with open(source_file, encoding="utf-8") as f:
    reader = csv.reader(f)

    header = next(reader)

    def parse_row(row: List[str]) -> Row:
        def parse_time(time_str: str) -> datetime:
            return datetime.strptime(time_str, default_time_format)

        # Name,Joined,Assigned,TA,Left
        name = row[0]
        join_time = parse_time(row[1])
        if row[2] == "-":
            assignment = None
        else:
            assignment = Assignment(time=parse_time(row[2]), assistant=row[3])
        disconnect_time = parse_time(row[4])

        return Row(name, join_time, assignment, disconnect_time)

    rows = [r for row in reader if not is_assistant((r := parse_row(row)).name)]

    names = set([name for r in rows if not is_assistant(name := r.name)])

    def num_questions_and_time_for(name: str) -> Tuple[int, timedelta]:
        relevant_events = [r for r in rows if r.name == name]
        return len(relevant_events), sum([r.question_duration for r in relevant_events], start=timedelta(0))

    num_questions_and_names = sorted(
        [(*num_questions_and_time_for(name), name) for name in names], key=lambda p: (-p[0], p[2].lower())
    )
    print(f"{len(names)} people asked questions:")
    for num, duration, name in num_questions_and_names:
        print(f"  {num:>2}  ({format_duration(duration)})  {name}")
    print("--\n")

    print(f"Details chronologically for {len(rows)} questions:")
    for r in rows:
        print(f"  {r}")

    wait_durations_gave_up: List[timedelta] = []
    wait_durations_served: List[timedelta] = []
    for r in rows:
        if r.was_served:
            wait_durations_served.append(r.wait_duration)
        else:
            wait_durations_gave_up.append(r.wait_duration)

    def mean_duration(durs: List[timedelta]) -> timedelta:
        total_secs = sum(durs, start=timedelta(0)).total_seconds()
        return timedelta(seconds=total_secs / len(durs))

    num_questions = len(rows)
    num_gave_up = len(wait_durations_gave_up)
    avg_wait_duration_gave_up = mean_duration(wait_durations_gave_up)
    num_served = len(wait_durations_served)
    avg_wait_duration_served = mean_duration(wait_durations_served)
    avg_wait_duration = mean_duration(wait_durations_gave_up + wait_durations_served)

    print("--")
    print(f"Mean wait durations:")
    print(f"  Overall:  {format_duration(avg_wait_duration)}  (N = {num_questions})")
    print(f"    Served: {format_duration(avg_wait_duration_served)}  (N = {num_served}, {int(100 * num_served / num_questions)}%)")
    print(f"    Gaveup: {format_duration(avg_wait_duration_gave_up)}  (N = {num_gave_up}, {int(100 * num_gave_up / num_questions)}%)")


    print("--")