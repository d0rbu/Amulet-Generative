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

def create_generate_groups(
    world: BaseLevel, dimension: Dimension, selection: SelectionGroup, options: dict
):
    contiguous_groups = contiguous_selections(selection)

    # TODO: create groups of size GENERATION_SIZE which cover the entire selection along with masks to generate the last 1 - GENERATION_CONTEXT_SIZE blocks along each axis

def operation(
    world: BaseLevel, dimension: Dimension, selection: SelectionGroup, options: dict
):
    # When the user presses the run button this function will be run as normal but
    # since the "options" key was defined in export this function will get another
    # input in the form of a dictionary where the keys are the same as you defined
    # them in the options dictionary above and the values are what the user picked
    # in the UI (bool, int, float, str)
    # If "options" is not defined in export this will just be an empty dictionary
    generate_groups, generate_masks = create_generate_groups(world, dimension, selection, options)

    # TODO: run these groups and masks thru the backend server to generate the structures

export = {
    "name": "Structure Generate",
    "operation": operation,
}
