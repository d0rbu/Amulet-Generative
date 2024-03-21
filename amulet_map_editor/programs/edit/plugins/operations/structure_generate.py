# Generate operation
import numpy as np

from amulet.api.data_types import BlockCoordinates, BlockCoordinatesNDArray, BlockCoordinatesAny
from amulet.api.selection import SelectionGroup, SelectionBox
from amulet.api.level import BaseLevel
from amulet.api.data_types import Dimension

from amulet_map_editor.programs.edit.api.operations.errors import (
    OperationError,
)


GENERATION_SIZE = (16, 16, 16)
GENERATION_CONTEXT_SIZE = (8, 8, 8)


def contiguous_selections(
    selection: SelectionGroup,
) -> list[SelectionGroup]:
    """
    Split the selection into contiguous selections
    :param selection: The selection to split
    :return: A list of contiguous selections
    """
    selections = []
    for box in selection.selection_boxes:
        if not selections:
            selections.append(SelectionGroup([box]))
        else:
            for sel in selections:
                if any(
                    box.intersects(sel_box)
                    for sel_box in sel.selection_boxes
                ):
                    sel.selection_boxes.append(box)
                    break
            else:
                selections.append(SelectionGroup([box]))
    return selections

def create_generate_boxes(
    world: BaseLevel,
    dimension: Dimension,
    selection: SelectionGroup,
    options: dict,
    generation_size: BlockCoordinates = GENERATION_SIZE,
    generation_context_size: BlockCoordinates = GENERATION_CONTEXT_SIZE,
) -> list[SelectionBox]:
    """
    Create the boxes and to generate the structures
    :param world: The world
    :param dimension: The dimension to generate the structures in
    :param selection: The selection to generate the structures in
    :param options: The options for the generation
    :return: A tuple of the boxes
    """
    contiguous_groups = contiguous_selections(selection)

    # TODO: create boxes of size GENERATION_SIZE which cover the entire selection to generate the last 1 - GENERATION_CONTEXT_SIZE blocks along each axis

def operation(
    world: BaseLevel, dimension: Dimension, selection: SelectionGroup, options: dict
) -> None:
    # When the user presses the run button this function will be run as normal but
    # since the "options" key was defined in export this function will get another
    # input in the form of a dictionary where the keys are the same as you defined
    # them in the options dictionary above and the values are what the user picked
    # in the UI (bool, int, float, str)
    # If "options" is not defined in export this will just be an empty dictionary
    generate_boxes = create_generate_boxes(world, dimension, selection, options)

    # TODO: run these boxes thru the backend server to generate the structures. must be done in YZX order

####### TESTS #######

def test_contiguous_selections_1():
    selection = SelectionGroup([])
    contiguous = contiguous_selections(selection)
    assert len(contiguous) == 0

def test_contiguous_selections_2():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (2, 2, 2)),
            SelectionBox((3, 3, 3), (5, 5, 5)),
            SelectionBox((6, 6, 6), (8, 8, 8)),
        ]
    )
    contiguous = contiguous_selections(selection)
    assert len(contiguous) == 3
    assert contiguous[0].selection_boxes == selection.selection_boxes[:1]
    assert contiguous[1].selection_boxes == selection.selection_boxes[1:2]
    assert contiguous[2].selection_boxes == selection.selection_boxes[2:]

def test_contiguous_selections_3():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (2, 2, 2)),
            SelectionBox((1, 1, 1), (2, 2, 2)),
        ]
    )
    contiguous = contiguous_selections(selection)
    assert len(contiguous) == 1
    assert contiguous[0].selection_boxes == selection.selection_boxes

def test_contiguous_selections_4():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (2, 2, 2)),
            SelectionBox((1, 1, 1), (2, 2, 2)),
            SelectionBox((1, 1, 1), (3, 3, 3)),
            SelectionBox((4, 4, 4), (5, 5, 5)),
            SelectionBox((5, 4, 4), (6, 6, 6)),
            SelectionBox((7, 7, 7), (8, 8, 8)),
        ]
    )
    contiguous = contiguous_selections(selection)
    assert len(contiguous) == 3
    assert contiguous[0].selection_boxes == selection.selection_boxes[:3]
    assert contiguous[1].selection_boxes == selection.selection_boxes[3:5]
    assert contiguous[2].selection_boxes == selection.selection_boxes[5:]

def test_contiguous_selections_5():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (2, 2, 2)),
            SelectionBox((2, 2, 1), (3, 3, 3)),
        ]
    )
    contiguous = contiguous_selections(selection)
    assert len(contiguous) == 2
    assert contiguous[0].selection_boxes == selection.selection_boxes[:1]
    assert contiguous[1].selection_boxes == selection.selection_boxes[1:]

def test_create_generate_boxes_1():
    selection = SelectionGroup([])
    generate_boxes = create_generate_boxes(None, None, selection, None)
    assert len(generate_boxes) == 0

def test_create_generate_boxes_2():
    selection = SelectionGroup(
        [
            SelectionBox((3, 3, 3), (5, 5, 5)),
        ]
    )
    generation_size = (4, 4, 4)
    generation_context_size = (2, 2, 2)
    generate_boxes = create_generate_boxes(None, None, selection, None, generation_size, generation_context_size)
    assert len(generate_boxes) == 1
    assert generate_boxes[0].min == (1, 1, 1)
    assert generate_boxes[0].max == (5, 5, 5)

def test_create_generate_boxes_3():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (2, 2, 2)),
            SelectionBox((3, 3, 3), (5, 5, 5)),
            SelectionBox((6, 6, 6), (8, 8, 8)),
        ]
    )
    generation_size = (4, 4, 4)
    generation_context_size = (2, 2, 2)
    generate_boxes = create_generate_boxes(None, None, selection, None, generation_size, generation_context_size)
    assert len(generate_boxes) == 3
    assert generate_boxes[0].min == (-2, -2, -2)
    assert generate_boxes[0].max == (2, 2, 2)
    assert generate_boxes[1].min == (1, 1, 1)
    assert generate_boxes[1].max == (5, 5, 5)
    assert generate_boxes[2].min == (4, 4, 4)
    assert generate_boxes[2].max == (8, 8, 8)
    
def test_create_generate_boxes_4():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (2, 2, 4)),
        ]
    )
    generation_size = (4, 4, 4)
    generation_context_size = (2, 2, 2)
    generate_boxes = create_generate_boxes(None, None, selection, None, generation_size, generation_context_size)
    assert len(generate_boxes) == 2
    assert generate_boxes[0].min == (-2, -2, -2)
    assert generate_boxes[0].max == (2, 2, 2)
    assert generate_boxes[1].min == (-2, -2, 0)
    assert generate_boxes[1].max == (2, 2, 4)

def test_create_generate_boxes_5():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (2, 4, 4)),
        ]
    )
    generation_size = (4, 4, 4)
    generation_context_size = (2, 2, 2)
    generate_boxes = create_generate_boxes(None, None, selection, None, generation_size, generation_context_size)
    assert len(generate_boxes) == 4 
    assert generate_boxes[0].min == (-2, -2, -2)
    assert generate_boxes[0].max == (2, 2, 2)
    assert generate_boxes[1].min == (-2, 0, -2)
    assert generate_boxes[1].max == (2, 4, 2)
    assert generate_boxes[2].min == (-2, -2, 0)
    assert generate_boxes[2].max == (2, 2, 4)
    assert generate_boxes[3].min == (-2, 0, 0)
    assert generate_boxes[3].max == (2, 4, 4)

def test_create_generate_boxes_6():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (4, 4, 4)),
        ]
    )
    generation_size = (4, 4, 4)
    generation_context_size = (2, 2, 2)
    generate_boxes = create_generate_boxes(None, None, selection, None, generation_size, generation_context_size)
    assert len(generate_boxes) == 8
    assert generate_boxes[0].min == (-2, -2, -2)
    assert generate_boxes[0].max == (2, 2, 2)
    assert generate_boxes[1].min == (0, -2, -2)
    assert generate_boxes[1].max == (4, 2, 2)
    assert generate_boxes[2].min == (-2, 0, -2)
    assert generate_boxes[2].max == (2, 4, 2)
    assert generate_boxes[3].min == (0, 0, -2)
    assert generate_boxes[3].max == (4, 4, 2)
    assert generate_boxes[4].min == (-2, -2, 0)
    assert generate_boxes[4].max == (2, 2, 4)
    assert generate_boxes[5].min == (0, -2, 0)
    assert generate_boxes[5].max == (4, 2, 4)
    assert generate_boxes[6].min == (-2, 0, 0)
    assert generate_boxes[6].max == (2, 4, 4)
    assert generate_boxes[7].min == (0, 0, 0)
    assert generate_boxes[7].max == (4, 4, 4)

def test_create_generate_boxes_7():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (2, 2, 2)),
            SelectionBox((1, 0, 1), (2, 2, 2)),
        ]
    )
    generation_size = (4, 4, 4)
    generation_context_size = (2, 2, 2)
    generate_boxes = create_generate_boxes(None, None, selection, None, generation_size, generation_context_size)
    assert len(generate_boxes) == 1
    assert generate_boxes[0].min == (-2, -2, -2)
    assert generate_boxes[0].max == (2, 2, 2)

def test_create_generate_boxes_8():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (2, 2, 2)),
            SelectionBox((1, 1, 1), (2, 2, 2)),
            SelectionBox((1, 1, 1), (3, 3, 3)),
            SelectionBox((4, 4, 4), (5, 5, 5)),
            SelectionBox((5, 5, 4), (6, 6, 6)),
            SelectionBox((7, 7, 7), (8, 8, 8)),
        ]
    )
    generation_size = (4, 4, 4)
    generation_context_size = (2, 2, 2)
    generate_boxes = create_generate_boxes(None, None, selection, None, generation_size, generation_context_size)
    assert len(generate_boxes) == 3
    assert generate_boxes[0].min == (-2, -2, -2)
    assert generate_boxes[0].max == (2, 2, 2)
    assert generate_boxes[1].min == (1, 1, 1)
    assert generate_boxes[1].max == (5, 5, 5)
    assert generate_boxes[2].min == (4, 4, 4)
    assert generate_boxes[2].max == (8, 8, 8)

def test_create_generate_boxes_9():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (2, 2, 2)),
            SelectionBox((1, 1, 1), (3, 3, 3)),
        ]
    )
    generation_size = (4, 4, 4)
    generation_context_size = (2, 2, 2)
    generate_boxes = create_generate_boxes(None, None, selection, None, generation_size, generation_context_size)
    assert len(generate_boxes) == 2
    assert generate_boxes[0].min == (-2, -2, -2)
    assert generate_boxes[0].max == (2, 2, 2)
    assert generate_boxes[1].min == (-1, -1, -1)
    assert generate_boxes[1].max == (3, 3, 3)

####### END TESTS #######

export = {
    "name": "Structure Generate",
    "operation": operation,
}
