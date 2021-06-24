import csv
import re
import uuid

from pya2l import DB, model
from pya2l.api import inspect
from sys import argv
from xml.etree.ElementTree import Element, SubElement, Comment, ElementTree

BASE_OFFSET = 0xA0800000
USE_CONSTANTS = (
    False
)  # Should we use "constants" / "scalars" in the XDF? They kind of aren't good at all...

db = DB()
# session = db.import_a2l(argv[1])
session = db.open_existing(argv[1])

data_sizes = {
    "UWORD": 2,
    "UBYTE": 1,
    "SBYTE": 1,
    "SWORD": 2,
    "ULONG": 4,
    "SLONG": 4,
    "FLOAT32_IEEE": 4,
}

# XDF Serialization methods

categories = []


def xdf_add_category(xdfheader, category):
    if category not in categories:
        categories.append(category)
        index = categories.index(category)
        xdf_category(xdfheader, category, index)


def xdf_root_with_configuration(title):
    root = Element("XDFFORMAT")
    root.set("version", "1.60")

    xdfheader = SubElement(root, "XDFHEADER")
    flags = SubElement(xdfheader, "flags")
    flags.text = "0x1"
    deftitle = SubElement(xdfheader, "deftitle")
    deftitle.text = title
    description = SubElement(xdfheader, "description")
    description.text = "Auto-generated by A2L2XDF"
    baseoffset = SubElement(xdfheader, "BASEOFFSET")
    baseoffset.set("offset", "0")
    baseoffset.set("subtract", "0")
    defaults = SubElement(xdfheader, "DEFAULTS")
    defaults.set("datasizeinbits", "8")
    defaults.set("sigdigits", "4")
    defaults.set("outputtype", "1")
    defaults.set("signed", "0")
    defaults.set("lsbfirst", "1")
    defaults.set("float", "0")
    region = SubElement(xdfheader, "REGION")
    region.set("type", "0xFFFFFFFF")
    region.set("startaddress", "0x0")
    region.set("size", "0x7D000")
    region.set("regionflags", "0x0")
    region.set("name", "Binary")
    region.set("desc", "BIN for the XDF")
    return [root, xdfheader]


def xdf_embeddeddata(element: Element, id, axis_def):
    embeddeddata = SubElement(element, "EMBEDDEDDATA")
    embeddeddata.set("mmedtypeflags", "0x02" if id != "z" else "0x06")
    embeddeddata.set("mmedaddress", str(axis_def["address"]))
    embeddeddata.set("mmedelementsizebits", str(data_sizes[axis_def["dataSize"]] * 8))
    embeddeddata.set(
        "mmedcolcount", str(axis_def["length"]) if "length" in axis_def else "1"
    )
    if id == "z":
        embeddeddata.set(
            "mmedrowcount", str(axis_def["rows"]) if "rows" in axis_def else "1"
        )
    embeddeddata.set("mmedmajorstridebits", str(data_sizes[axis_def["dataSize"]] * 8))
    embeddeddata.set("mmedminorstridebits", "0")
    return embeddeddata


def fake_xdf_axis_with_size(table: Element, id, size):
    axis = SubElement(table, "XDFAXIS")
    axis.set("uniqueid", "0x0")
    axis.set("id", id)
    indexcount = SubElement(axis, "indexcount")
    indexcount.text = str(size)
    outputtype = SubElement(axis, "outputtype")
    outputtype.text = "4"
    dalink = SubElement(axis, "DALINK")
    dalink.set("index", "0")
    math = SubElement(axis, "MATH")
    math.set("equation", "X")
    var = SubElement(math, "VAR")
    var.set("id", "X")
    for label_index in range(size):
        label = SubElement(axis, "LABEL")
        label.set("index", str(label_index))
        label.set("value", "-")
    return axis


def xdf_axis_with_table(table: Element, id, axis_def):
    axis = SubElement(table, "XDFAXIS")
    axis.set("uniqueid", "0x0")
    axis.set("id", id)

    xdf_embeddeddata(axis, id, axis_def)

    indexcount = SubElement(axis, "indexcount")
    indexcount.text = str(axis_def["length"]) if "length" in axis_def else "1"
    min = SubElement(axis, "min")
    min.text = str(axis_def["min"])
    max = SubElement(axis, "max")
    max.text = str(axis_def["max"])
    units = SubElement(axis, "units")
    units.text = axis_def["units"]
    embedinfo = SubElement(axis, "embedinfo")
    embedinfo.set("type", "1")  # "Pure, Internal"
    dalink = SubElement(axis, "DALINK")
    dalink.set("index", "0")
    math = SubElement(axis, "MATH")
    math.set("equation", axis_def["math"])
    var = SubElement(math, "VAR")
    var.set("id", "X")
    return axis


def xdf_table_with_root(root: Element, table_def):
    table = SubElement(root, "XDFTABLE")
    table.set("uniqueid", table_def["z"]["address"])
    table.set("flags", "0x30")
    title = SubElement(table, "title")
    title.text = table_def["title"]
    description = SubElement(table, "description")
    description.text = table_def["description"]
    categorymem = SubElement(table, "CATEGORYMEM")
    categorymem.set("index", "0")
    categorymem.set("category", str(table_def["category"] + 1))
    if "sub_category" in table_def:
        categorymem = SubElement(table, "CATEGORYMEM")
        categorymem.set("index", "1")
        categorymem.set("category", str(table_def["sub_category"] + 1))
    return table


def xdf_constant_with_root(root: Element, table_def):
    table = SubElement(root, "XDFCONSTANT")
    table.set("uniqueid", table_def["z"]["address"])
    title = SubElement(table, "title")
    title.text = table_def["title"]
    description = SubElement(table, "description")
    description.text = table_def["description"]
    categorymem = SubElement(table, "CATEGORYMEM")
    categorymem.set("index", "0")
    categorymem.set("category", str(table_def["category"] + 1))
    if "sub_category" in table_def:
        categorymem = SubElement(table, "CATEGORYMEM")
        categorymem.set("index", "1")
        categorymem.set("category", str(table_def["sub_category"] + 1))

    xdf_embeddeddata(table, "z", table_def["z"])

    math = SubElement(table, "MATH")
    math.set("equation", table_def["z"]["math"])
    var = SubElement(math, "VAR")
    var.set("id", "X")

    return table


def xdf_table_from_axis(root: Element, table_def, axis_name):
    table = SubElement(root, "XDFTABLE")
    table.set("uniqueid", table_def[axis_name]["address"])
    table.set("flags", "0x30")
    title = SubElement(table, "title")
    title.text = (
        f'{table_def["title"]} : {axis_name} axis : {table_def[axis_name]["name"]}'
    )
    description = SubElement(table, "description")
    description.text = table_def[axis_name]["name"]
    categorymem = SubElement(table, "CATEGORYMEM")
    categorymem.set("index", "0")
    categorymem.set("category", str(table_def["category"] + 1))
    categorymem = SubElement(table, "CATEGORYMEM")
    categorymem.set("index", "1")
    categorymem.set("category", str(categories.index("Axis") + 1))
    fake_xdf_axis_with_size(table, "x", table_def[axis_name]["length"])
    fake_xdf_axis_with_size(table, "y", 1)
    xdf_axis_with_table(table, "z", table_def[axis_name])
    return table


def xdf_category(xdfheader: Element, category_name, category_index):
    category = SubElement(xdfheader, "CATEGORY")
    category.set("index", hex(category_index))
    category.set("name", category_name)
    return category


# Helpers


def calc_map_size(characteristic: inspect.Characteristic):
    data_size = data_sizes[characteristic.deposit.fncValues["datatype"]]
    map_size = data_size
    for axis_ref in characteristic.axisDescriptions:
        map_size *= axis_ref.maxAxisPoints
    return map_size


def adjust_address(address):
    return address - BASE_OFFSET


# A2L to "normal" conversion methods


def fix_degree(bad_string):
    return re.sub(
        "\uFFFD", "\u00B0", bad_string
    )  # Replace Unicode "unknown" with degree sign


def axis_ref_to_dict(axis_ref: inspect.AxisDescr):
    axis_value = {
        "name": axis_ref.axisPtsRef.name,
        "units": fix_degree(axis_ref.axisPtsRef.compuMethod.unit),
        "min": axis_ref.lowerLimit,
        "max": axis_ref.upperLimit,
        "address": hex(
            adjust_address(axis_ref.axisPtsRef.address)
            + data_sizes[axis_ref.axisPtsRef.depositAttr.axisPts["x"]["datatype"]]
        ),  # We need to offset the axis by 1 value, the first value is another length
        "length": axis_ref.maxAxisPoints,
        "dataSize": axis_ref.axisPtsRef.depositAttr.axisPts["x"]["datatype"],
    }
    if len(axis_ref.compuMethod.coeffs) > 0:
        axis_value["math"] = coefficients_to_equation(axis_ref.compuMethod.coeffs)
    else:
        axis_value["math"] = "X"
    return axis_value


def coefficients_to_equation(coefficients):
    a, b, c, d, e, f = (
        str(coefficients["a"]),
        str(coefficients["b"]),
        str(coefficients["c"]),
        str(coefficients["d"]),
        str(coefficients["e"]),
        str(coefficients["f"]),
    )
    if a == "0.0" and d == "0.0":  # Polynomial is of order 1, ie linear
        return f"(({f} * X) - {c} ) / ({b} - ({e} * X))"
    else:
        return "Cannot handle polynomial ratfunc because we do not know how to invert!"


# Begin

root, xdfheader = xdf_root_with_configuration(argv[1])
xdf_add_category(xdfheader, "Axis")

with open(argv[2], encoding="utf-8-sig") as csvfile:
    csvreader = csv.DictReader(csvfile)
    for row in csvreader:
        tablename = row["Table Name"]
        category = row["Category"]
        sub_category = row["Sub Category"]
        characteristics = (
            session.query(model.Characteristic)
            .order_by(model.Characteristic.name)
            .filter(model.Characteristic.name == tablename)
            .first()
        )
        if characteristics is None:
            print("******** Could not find ! ", tablename)
            continue
        c_data = inspect.Characteristic(session, tablename)
        table_offset = adjust_address(c_data.address)
        table_length = calc_map_size(c_data)
        axisDescriptions = c_data.axisDescriptions

        xdf_add_category(xdfheader, category)

        table_def = {
            "title": c_data.longIdentifier,
            "description": c_data.name,
            "category": categories.index(category),
            "z": {
                "min": c_data.lowerLimit,
                "max": c_data.upperLimit,
                "address": hex(adjust_address(c_data.address)),
                "dataSize": c_data.deposit.fncValues["datatype"],
                "units": fix_degree(c_data.compuMethod.unit),
            },
        }

        if sub_category is not None and len(sub_category) > 0:
            xdf_add_category(xdfheader, sub_category)
            table_def["sub_category"] = categories.index(sub_category)

        if len(c_data.compuMethod.coeffs) > 0:
            table_def["z"]["math"] = coefficients_to_equation(c_data.compuMethod.coeffs)
        else:
            table_def["z"]["math"] = "X"

        if len(axisDescriptions) == 0 and USE_CONSTANTS is True:
            table_def["constant"] = True
        if len(axisDescriptions) > 0:
            table_def["x"] = axis_ref_to_dict(axisDescriptions[0])
            table_def["z"]["length"] = table_def["x"]["length"]
            table_def["description"] += f'\nX: {table_def["x"]["name"]}'
        if len(axisDescriptions) > 1:
            table_def["y"] = axis_ref_to_dict(axisDescriptions[1])
            table_def["description"] += f'\nY: {table_def["y"]["name"]}'
            table_def["z"]["rows"] = table_def["y"]["length"]

        if "constant" in table_def:
            constant = xdf_constant_with_root(root, table_def)
        else:
            table = xdf_table_with_root(root, table_def)

            if "x" in table_def:
                xdf_axis_with_table(table, "x", table_def["x"])
                if row["Generate X Axis"] == "True":
                    xdf_table_from_axis(root, table_def, "x")
            else:
                fake_xdf_axis_with_size(table, "x", 1)

            if "y" in table_def:
                xdf_axis_with_table(table, "y", table_def["y"])
                if row["Generate Y Axis"] == "True":
                    xdf_table_from_axis(root, table_def, "y")
            else:
                fake_xdf_axis_with_size(table, "y", 1)

            xdf_axis_with_table(table, "z", table_def["z"])

ElementTree(root).write(f"{argv[1]}.xdf")
