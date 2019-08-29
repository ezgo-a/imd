import struct
import functools
from copy import deepcopy


@functools.total_ordering
class Time(object):
    """Time object , int = ms, list = [min, second, ms], default is 1s."""
    def __init__(self, time):
        if isinstance(time, int) or isinstance(time, float):
            self.ms = round(time)
            minute = self.ms // 60000
            second = (self.ms - minute * 60000) // 1000
            ms = self.ms - minute * 60000 - second * 1000
            self.ll = [minute, second, ms]
        elif isinstance(time, list):
            self.ms = round((time[0] * 60 + time[1]) * 1000 + time[2])
            minute = self.ms // 60000
            second = (self.ms - minute * 60000) // 1000
            ms = self.ms - minute * 60000 - second * 1000
            self.ll = [minute, second, ms]

    def __repr__(self):
        return '{}'.format(self.ll)

    def __add__(self, other):
        if isinstance(other, Time):
            return Time(self.ms + other.ms)
        else:
            return Time(self.ms + Time(other).ms)

    def __truediv__(self, other):
        return Time(self.ms/other)

    def __sub__(self, other):
        if isinstance(other, Time):
            return Time(self.ms - other.ms)
        else:
            return Time(self.ms - Time(other).ms)

    def __mul__(self, other):
        return Time(self.ms*other)

    def __radd__(self, other):
        return Time(self.ms + Time(other))

    def __rmul__(self, other):
        return Time(self.ms*other)

    def __eq__(self, other):
        if isinstance(other, Time):
            return self.ms == other.ms
        else:
            return self.ms == Time(other).ms

    def __lt__(self, other):
        if isinstance(other, Time):
            return self.ms < other.ms
        else:
            return self.ms < Time(other).ms


class TimeList(list):
    def __init__(self, *args):
        if args == ():
            super().__init__(args)
        elif len(args) == 1 and isinstance(args[0], list):
            g = [Time(x) for x in args[0]]
            super().__init__(g)
        else:
            g = [Time(x) for x in args]
            super().__init__(g)

    def insert(self, index, time):
        if isinstance(time, Time):
            super().insert(index, time)
        else:
            super().insert(index, Time(time))

    def append(self, time):
        if isinstance(time, Time):
            return super().append(time)
        else:
            return super().append(Time(time))

    def extend(self, time_list):
        for x in time_list:
            self.append(x)

    def __add__(self, other):
        for i in range(0, len(self)):
            self[i] = self[i] + other
        return self

    def __mul__(self, other):
        for i in range(0, len(self)):
            self[i] = self[i] * other
        return self

    def __sub__(self, other):
        for i in range(0, len(self)):
            self[i] = self[i] - other
        return self

    def __truediv__(self, other):
        for i in range(0, len(self)):
            self[i] = self[i]/other
        return self


class Trace(object):
    def __init__(self, action_type, action_time, action_parameters):
        """Those parameters are in list, elements in bytes"""
        self.action_type = action_type
        self.action_time = action_time
        self.action_parameters = action_parameters

    def correct(self, _correction):
        for i in range(len(self.action_type)):
            if self.action_type[i] == b'\x62\x00' or self.action_type[i] == b'\x22\x00':
                start = self.action_time[i].ms
                dt = int.from_bytes(self.action_parameters[i][1:], byteorder='little')
                cor = round(_correction.correct(dt))
                start_next = start + cor
                column = self.action_parameters[i][0]
                self.action_parameters[i] = int.to_bytes(column, 1, byteorder='little')
                self.action_parameters[i] += int.to_bytes(cor, 4, byteorder='little')
                self.action_time[i+1] = Time(start_next)


class Correction(object):
    def __init__(self, max_ms, n, p=0.7, bpm=150):
        self.max_ms = max_ms
        self.n = n
        self.p = p
        self.delta = 15000//bpm
        self.delta1 = round(15000*p//bpm)
        self.f = lambda x: self.delta1 - pow(self.delta1 - x, n)/pow(self.delta1 - self.max_ms, n - 1)

    def correct(self, dt):
        if dt < self.delta:
            return dt
        i = 0
        while dt > i*self.delta - 1:
            i += 1
        # (i-1)*delta <= dt <= i*delta - 1
        if dt - (i-1)*self.delta < self.max_ms:
            return (i-1)*self.delta - 1
        elif self.max_ms <= dt - (i-1)*self.delta <= self.delta1:
            correction = round(self.f(dt-(i-1)*self.delta))
            if correction == self.delta:
                correction = self.delta - 1
            return (i-1)*self.delta + correction
        else:
            return dt

    def bpm_update(self, bpm):
        self.delta = 15000//bpm
        self.delta1 = round(15000*self.p//bpm)
        self.f = lambda x: self.delta1 - pow(self.delta1 - x, self.n)/pow(self.delta1 - self.max_ms, self.n - 1)


class Imd(object):
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as imd:
            temp = imd.read(4)
            tot_time = Time((int.from_bytes(temp, byteorder='little')))
            temp = imd.read(4)
            tot_lines = int.from_bytes(temp, byteorder='little')
            time_list = TimeList()
            bpm_list = list()
            for i in range(0, tot_lines):
                temp = imd.read(4)
                time_list.append((int.from_bytes(temp, byteorder='little')))
                temp = imd.read(8)
                bpm, = struct.unpack('d', temp)
                bpm_list.append(bpm)
            # unknown = (b'\x03\x03' == imd.read(2))
            imd.read(2)
            temp = imd.read(4)
            tot_actions = int.from_bytes(temp, byteorder='little')
            action_type_list = list()
            action_time_list = TimeList()
            action_parameters_list = list()
            for j in range(0, tot_actions):
                temp = imd.read(2)
                action_type_list.append(temp)
                temp = imd.read(4)
                action_time_list.append(int.from_bytes(temp, byteorder='little'))
                temp = imd.read(5)
                action_parameters_list.append(temp)
        self.tot_time = tot_time
        self.time_list = time_list
        self.action_type_list = action_type_list
        self.action_time_list = action_time_list
        self.action_parameters_list = action_parameters_list
        self.traces = []
        self.bpm_list = []
        for i in range(len(time_list)):
            tup = (bpm_list[i], time_list[i].ms)
            self.bpm_list.append(tup)

    def info(self):
        print('Path: ', self.path)
        print('Total time: ', self.tot_time)
        print('Bpm: ', self.bpm_list)

    def reordering(self):
        sort_list = []
        for i in range(len(self.action_parameters_list)):
            tup = (self.action_time_list[i], self.action_type_list[i], self.action_parameters_list[i])
            sort_list.append(tup)
        sort_list.sort(key=lambda x: x[0])
        self.action_time_list = []
        self.action_type_list = []
        self.action_parameters_list = []
        for i in range(len(sort_list)):
            self.action_time_list.append(sort_list[i][0])
            self.action_type_list.append(sort_list[i][1])
            self.action_parameters_list.append(sort_list[i][2])

    @staticmethod
    def new_time_list(bpm_list, tot_time):
        """Bpm in the form [(bpm1,time1), (bpm,time2), ...] 0ms=time1<time2<...; time1, ... and tot_time are in ms"""
        time_list = TimeList([0])
        new_bpm_list = [bpm_list[0][0], ]
        for i in range(0, len(bpm_list)):
            delta = 60000/bpm_list[i][0]
            if i == len(bpm_list) - 1:
                end = tot_time
            else:
                end = bpm_list[i+1][1]
            while time_list[-1] < end:
                time_list.append(time_list[-1]+delta)
                new_bpm_list.append(bpm_list[i][0])
        for i in range(len(new_bpm_list)):
            new_bpm_list[i] = (new_bpm_list[i], time_list[i].ms)
        return time_list, new_bpm_list

    def split_traces(self):
        self.traces = []
        self.reordering()
        idx = 0
        tot_length = len(self.action_time_list)
        while idx < tot_length:
            if self.action_type_list[idx] == b'\x00\x00' or self.action_type_list[idx] == b'\x01\x00' or\
                    self.action_type_list[idx] == b'\x02\x00':
                idx += 1
                continue
            else:
                actions = []
                times = []
                parameters = []
                column = self.action_parameters_list[idx][0]
                if self.action_type_list[idx] == b'\x61\x00':
                    move = int.from_bytes(self.action_parameters_list[idx][1:], byteorder='little', signed=True)
                    column += move
                actions.append(self.action_type_list.pop(idx))
                times.append(self.action_time_list.pop(idx))
                parameters.append(self.action_parameters_list.pop(idx))
                tot_length -= 1
                y = deepcopy(idx)
                while y < tot_length:
                    if self.action_parameters_list[y][0] != column:
                        y += 1
                        continue
                    else:
                        if self.action_type_list[y] == b'\x21\x00' or self.action_type_list[y] == b'\x22\x00':
                            if self.action_type_list[y] == b'\x21\x00':
                                move = int.from_bytes(self.action_parameters_list[y][1:],
                                                      byteorder='little', signed=True)
                                column += move
                            actions.append(self.action_type_list.pop(y))
                            times.append(self.action_time_list.pop(y))
                            parameters.append(self.action_parameters_list.pop(y))
                            tot_length -= 1
                        elif self.action_type_list[y] == b'\xa1\x00' or self.action_type_list[y] == b'\xa2\x00':
                            actions.append(self.action_type_list.pop(y))
                            times.append(self.action_time_list.pop(y))
                            parameters.append(self.action_parameters_list.pop(y))
                            tot_length -= 1
                            self.traces.append(Trace(actions, times, parameters))
                            break

    def merge_traces(self):
        for trace in self.traces:
            self.action_type_list += trace.action_type
            self.action_parameters_list += trace.action_parameters
            self.action_time_list += trace.action_time
        self.traces = []
        self.reordering()

    def correct(self, _correction):
        copy_bpm_list = deepcopy(self.bpm_list)
        _correction.bpm_update(copy_bpm_list[0][0])
        copy_bpm_list.pop(0)
        for trace in self.traces:
            trace_start_time = trace.action_time[0].ms
            if trace_start_time >= copy_bpm_list[0][1]:
                _correction.bpm_update(copy_bpm_list[0][0])
                copy_bpm_list.pop(0)
            trace.correct(_correction)

    @staticmethod
    def get_time_lines(time_list, bpm_list):
        time_lines = []
        bpm_lines = []
        for i in range(len(time_list)):
            time = time_list[i].ms
            bpm = bpm_list[i][0]
            time_lines.append(int.to_bytes(time, 4, byteorder='little'))
            bpm_lines.append(struct.pack('d', bpm))
        return time_lines, bpm_lines

    def save(self, path):
        self.merge_traces()
        with open(path, 'wb') as fp:
            temp = int.to_bytes(self.tot_time.ms, 4, byteorder='little')
            fp.write(temp)
            time_lines, bpm_lines = self.get_time_lines(self.time_list, self.bpm_list)
            temp = int.to_bytes(len(time_lines), 4, byteorder='little')
            fp.write(temp)
            for i in range(len(time_lines)):
                fp.write(time_lines[i])
                fp.write(bpm_lines[i])
            fp.write(b'\x03\x03')
            temp = int.to_bytes(len(self.action_parameters_list), 4, byteorder='little')
            fp.write(temp)
            for i in range(len(self.action_type_list)):
                fp.write(self.action_type_list[i])
                fp.write(int.to_bytes(self.action_time_list[i].ms, 4, byteorder='little'))
                fp.write(self.action_parameters_list[i])


if __name__ == '__main__':
    read_path = 'E://Rmaster/imdLib/ezgo_data/drawing_5k_ez.imd'
    save_path = 'E://Rmaster/imdLib/ezgo_data/drawing1_5k_ez.imd'
    # read_path = 'E://Rmaster/imdLib/xueyuan_4k_hd.imd'
    # save_path = 'E://Rmaster/imdLib/xueyuan1_4k_hd.imd'
    xy = Imd(read_path)
    # Change BPM only. For example, 128 bpm from 0ms, 150 bpm from 1 min 30 s
    bpm_list0 = [(128, 0), (150, Time([0, 1, 30]).ms), ]
    new_time_list1, new_bpm_list1 = xy.new_time_list(bpm_list0, xy.tot_time.ms)
    xy.time_list = new_time_list1
    xy.bpm_list = new_bpm_list1
    xy.save(save_path)
    # Correct only.
    u_correction = Correction(5, 1.5, 0.7)
    xy.split_traces()
    xy.correct(u_correction)
    xy.merge_traces()
    xy.save(save_path)
