import math

import re

line_pattern = re.compile(r"""^
(?P<record_number>\d+)\t
(?P<transducer_top>[-+]?\d+)\t
(?P<transducer_bottom>[-+]?\d+)\t
(?P<temperature_voltage>[-+]?\d+)\t
(?P<button>[-+]?\d+)\t
ISHPR,
(?P<heading>[+-]?[0-9]+\.?[0-9]*|\.[0-9]+),
(?P<pitch>[+-]?[0-9]+\.?[0-9]*|\.[0-9]+),
(?P<roll>[+-]?[0-9]+\.?[0-9]*|\.[0-9]+)\s
[0-9a-fA-F]{2}\t #checksum
ISDPT,
(?P<depth_top>[+-]?[0-9]+\.?[0-9]*|\.[0-9]+),M,
(?P<pressure_top>[+-]?[0-9]+\.?[0-9]*|\.[0-9]+),B,
(?P<temperature_top>[+-]?[0-9]+\.?[0-9]*|\.[0-9]+),C\s
[0-9a-fA-F]{2}\t  #checksum
ISDPT,
(?P<depth_bottom>[+-]?[0-9]+\.?[0-9]*|\.[0-9]+),M,
(?P<pressure_bottom>[+-]?[0-9]+\.?[0-9]*|\.[0-9]+),B,
(?P<temperature_bottom>[+-]?[0-9]+\.?[0-9]*|\.[0-9]+),C\s
[0-9a-fA-F]{2} #checksum
""", re.VERBOSE|re.ASCII)


class ParseException(Exception):
    pass


def parseRecord(line, offsets):

    line = str(line)

    record = line_pattern.match(line)

    if record is None:
        raise ParseException("%d - %s" % (len(line), line))

    record = record.groupdict()

    #convert all to floats.
    record.update((k, float(v)) for k, v in record.items())

    return record

