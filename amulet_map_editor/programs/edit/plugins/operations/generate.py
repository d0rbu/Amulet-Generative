# Generate operation

from amulet.api.data_types import BlockCoordinates, BlockCoordinatesNDArray, BlockCoordinatesAny
from amulet.api.selection import SelectionGroup, SelectionBox
from amulet.api.level import BaseLevel
from amulet.api.data_types import Dimension

from amulet_map_editor.programs.edit.api.operations.errors import (
    OperationError,
)


GENERATION_SIZE = (16, 16, 16)

generation_size_string = "x".join(map(str, GENERATION_SIZE))


# TODO: use a defaultoperationui
def operation(
    world: BaseLevel, dimension: Dimension, selection: SelectionGroup, options: dict
):
    # When the user presses the run button this function will be run as normal but
    # since the "options" key was defined in export this function will get another
    # input in the form of a dictionary where the keys are the same as you defined
    # them in the options dictionary above and the values are what the user picked
    # in the UI (bool, int, float, str)
    # If "options" is not defined in export this will just be an empty dictionary
    if len(selection) <= 0:
        raise OperationError("No selection made")

    generate_box = selection[0]
    if len(selection) == 1:
        context_box = SelectionBox(
            generate_box.min, (generate_box.max_x, generate_box.min_y, generate_box.max_z)
        )
    else:
        context_box = selection[1]
    
    # TODO: extract blocks from selections, tokenize, and send to server

export = {
    "name": "Structure Generate",
    "operation": operation,
    "options": {},  # The options you defined above should be added here to show in the UI
}
