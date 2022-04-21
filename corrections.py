import math


class ParseException(Exception):
    pass


def verify_checksum(message):
    calc_cksum = 0
    for s in message[:-3]:
        calc_cksum ^= ord(s)
    return message[-2:].lower() == f"{calc_cksum:02x}"


def parse_hpr(message):
    values = message[:-3].split(",")
    if (len(values) < 4) or (not verify_checksum(message)):
        return ["nan", "nan", "nan"]
    return values[1:]


def parse_dpt(message):
    values = message[:-3].split(",")
    if (len(values) < 7) or (not verify_checksum(message)):
        return ["nan", "nan", "nan"]
    return values[1:6:2]


def robust_float(s):
    try:
        return float(s)
    except:
        return math.nan


def parseRecord(line, offsets):

    line = str(line)

    fields = line.split("\t")

    if len(fields) < 8:
        raise ParseException("too few fields in line %d - %s" % (len(fields), line))

    hpr = parse_hpr(fields[5])
    dpt_top = parse_dpt(fields[6])
    dpt_bottom = parse_dpt(fields[7])

    record = {
        "record_number": fields[0],
        "transducer_top": fields[1],
        "transducer_bottom": fields[2],
        "temperature_voltage": fields[3],
        "button": fields[4],
        "heading": hpr[0],
        "pitch": hpr[1],
        "roll": hpr[2],
        "depth_top": dpt_top[0],
        "pressure_top": dpt_top[1],
        "temperature_top": dpt_top[2],
        "depth_bottom": dpt_bottom[0],
        "pressure_bottom": dpt_bottom[1],
        "temperature_bottom": dpt_bottom[2],
    }

    # convert all to floats.
    record.update((k, robust_float(v)) for k, v in record.items())

    # add room for external encoder read-out
    record["depth_winch"] = math.nan

    # add calculated terms

    record["delta_pressure"] = record["pressure_bottom"] - record["pressure_top"]

    # TODO: apply calibrations to raw measurements.


    return record
