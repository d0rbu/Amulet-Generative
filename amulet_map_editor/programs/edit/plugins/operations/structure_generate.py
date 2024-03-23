# Generate operation
import numpy as np
from itertools import product

from amulet.api.data_types import BlockCoordinates, BlockCoordinatesNDArray, BlockCoordinatesAny
from amulet.api.selection import SelectionGroup, SelectionBox
from amulet.api.level import BaseLevel
from amulet.api.data_types import Dimension

from amulet_map_editor.programs.edit.api.operations.errors import (
    OperationError,
)


GENERATION_SIZE = (16, 16, 16)
GENERATION_CONTEXT_SIZE = (8, 8, 8)


def touches_or_intersects(group1: SelectionGroup, group2: SelectionGroup) -> bool:
    return any(
        box1.touches_or_intersects(box2) for box1, box2 in product(group1.selection_boxes, group2.selection_boxes)
    )

def volume(group: SelectionGroup) -> int:
    """
    Calculate the volume of the selection. Takes overlapping boxes into account
    :param group: The selection group
    :return: The volume of the selection
    """
    if len(group.selection_boxes) == 0:
        return 0

    total_coverage = np.zeros((group.max_x - group.min_x, group.max_y - group.min_y, group.max_z - group.min_z), dtype=bool)
    for box in group.selection_boxes:
        total_coverage[box.min_x - group.min_x : box.max_x - group.min_x, box.min_y - group.min_y : box.max_y - group.min_y, box.min_z - group.min_z : box.max_z - group.min_z] = True
    
    return np.sum(total_coverage)

def merge_boxes(group: SelectionGroup) -> SelectionGroup:
    """
    Remove redundant overlapping boxes
    :param group: The group of boxes to merge
    :return: The merged group
    """
    current_group = SelectionGroup(group.selection_boxes)

    while True:
        for i, box in enumerate(current_group.selection_boxes):
            if i == len(current_group.selection_boxes) - 1:
                test_group = SelectionGroup(current_group.selection_boxes[:i])
            else:
                test_group = SelectionGroup(current_group.selection_boxes[:i] + current_group.selection_boxes[i + 1 :])
            
            if volume(test_group) == volume(current_group):
                current_group = test_group
                break
        else:
            break

    return current_group


def contiguous_selections(
    selection: SelectionGroup,
) -> list[SelectionGroup]:
    """
    Split the selection into contiguous selections
    :param selection: The selection to split
    :return: A list of contiguous selections
    """
    old_selections = [SelectionGroup([box]) for box in selection.selection_boxes]
    new_selections = []

    # iteratively merge selections until no more merges can be made
    while True:
        for old_selection in old_selections:
            for i, new_selection in enumerate(new_selections):
                if old_selection is new_selection:
                    break

                if touches_or_intersects(old_selection, new_selection):
                    new_selections[i] = merge_boxes(new_selection + old_selection.selection_boxes)
                    break
            else:
                new_selections.append(old_selection)

        if len(new_selections) == len(old_selections):
            break

        old_selections = new_selections

    # merge boxes
    selections = [merge_boxes(old_selection) for old_selection in old_selections]

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
    assert len(contiguous[0].selection_boxes) == 1
    assert contiguous[0].selection_boxes[0] == SelectionBox((0, 0, 0), (2, 2, 2))

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
    assert contiguous[0].selection_boxes == selection.selection_boxes[:1] + selection.selection_boxes[2:3]
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
    assert len(contiguous) == 1
    assert contiguous[0].selection_boxes == selection.selection_boxes

# corner touching boxes are contiguous
def test_contiguous_selections_6():
    selection = SelectionGroup(
        [
            SelectionBox((0, 0, 0), (2, 2, 2)),
            SelectionBox((2, 2, 2), (3, 3, 3)),
        ]
    )
    contiguous = contiguous_selections(selection)
    assert len(contiguous) == 1
    assert contiguous[0].selection_boxes == selection.selection_boxes

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
