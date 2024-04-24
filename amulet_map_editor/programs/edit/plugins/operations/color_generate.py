# Generate operation

import os
import requests
import json
import numpy as np
from itertools import product
from typing import Generator

from amulet.api.data_types import BlockCoordinates, BlockCoordinatesNDArray, BlockCoordinatesAny
from amulet.api.selection import SelectionGroup, SelectionBox
from amulet.api.level import BaseLevel
from amulet.api.data_types import Dimension
from amulet.api import Block
from structure_generate import create_generate_boxes_with_direction, GENERATION_CONTEXT_SIZE, GENERATION_SIZE

from amulet_map_editor.programs.edit.api.operations.errors import (
    OperationError,
)


FILE_DIR = os.path.dirname(__file__)

with open(os.path.join(FILE_DIR, "block_map.json"), "r") as f:
    BLOCK_TO_ID_MAP = json.load(f)
_BLOCK_TO_ID_MAP = { k.replace(" ", "_"): v for k, v in BLOCK_TO_ID_MAP.items() }
BLOCK_TO_ID_MAP.update(_BLOCK_TO_ID_MAP)  # add copies of blocks with spaces replaced with underscores

with open(os.path.join(FILE_DIR, "block_ids_purged.json"), "r") as f:
    ID_TO_BLOCK_MAP = { int(k): v for k, v in json.load(f).items() }

def name_to_id(name: str) -> int:
    return BLOCK_TO_ID_MAP[name]

def id_to_block(ind: str) -> Block:
    block_id = ID_TO_BLOCK_MAP[ind]
    return Block.from_string_blockstate(block_id)


def operation(
    world: BaseLevel, dimension: Dimension, selection: SelectionGroup, options: dict
) -> Generator[float, None, None]:
    try:
        inpaint_strength = float(options["Inpaint Strength"])
        assert 0 <= inpaint_strength <= 1
    except (ValueError, AssertionError):
        raise OperationError("Inpaint Strength must be a float between 0 and 1")

    # When the user presses the run button this function will be run as normal but
    # since the "options" key was defined in export this function will get another
    # input in the form of a dictionary where the keys are the same as you defined
    # them in the options dictionary above and the values are what the user picked
    # in the UI (bool, int, float, str)
    # If "options" is not defined in export this will just be an empty dictionary
    generate_boxes, context_sign = create_generate_boxes_with_direction(world, dimension, selection, options)

    endpoint = options["Endpoint"]
    endpoint = f"{endpoint}/color"

    for i, (box, box_generation_context_size) in enumerate(generate_boxes):
        x_generator = range(box.min_x, box.max_x)
        y_generator = range(box.min_y, box.max_y)
        z_generator = range(box.min_z, box.max_z)

        if context_sign[0] < 0:
            x_generator = reversed(x_generator)
        if context_sign[1] < 0:
            y_generator = reversed(y_generator)
        if context_sign[2] < 0:
            z_generator = reversed(z_generator)

        blocks = np.empty((len(y_generator), len(z_generator), len(x_generator)), dtype=np.int16)
        for world_y, world_z, world_x in product(y_generator, z_generator, x_generator):
            y, z, x = world_y - box.min_y, world_z - box.min_z, world_x - box.min_x
            blocks[y, z, x] = name_to_id(world.get_block(world_x, world_y, world_z, dimension).base_name)

        generation_mask = blocks > 0
        blocks[box_generation_context_size[1]:, box_generation_context_size[2]:, box_generation_context_size[0]:] = -1  # set the context to -1
        blocks = blocks.tolist()

        num_steps = options["Steps"]

        data = {
            "data": [blocks],
            "y": 0,
            "steps": num_steps,
            "strength": inpaint_strength,
        }

        stream_response = requests.post(endpoint, json=data, stream=True)
        stream_response_iter = stream_response.iter_lines()

        for j, noised_sample in enumerate(stream_response_iter):
            yield (i + j / num_steps) / len(generate_boxes)

            generated_blocks = json.loads(noised_sample)

            for local_coordinates, block_id in generated_blocks:
                if not generation_mask[local_coordinates[4], local_coordinates[2], local_coordinates[3]]:
                    continue  # we are not to generate on air blocks

                coordinates = (
                    box.min_x + local_coordinates[4],
                    box.min_y + local_coordinates[2],
                    box.min_z + local_coordinates[3],
                )
                if coordinates in selection:
                    block = id_to_block(block_id)

                    world.set_version_block(
                        coordinates[0],
                        coordinates[1],
                        coordinates[2],
                        dimension,
                        version=("java", (1, 16, 2)),
                        block=block,
                    )
                else:
                    import pdb; pdb.set_trace()

export = {
    "name": "Color Generative Fill",
    "operation": operation,
    "options": {
        "X Context Length": ["int", -GENERATION_CONTEXT_SIZE[0]],
        "Y Context Length": ["int", -GENERATION_CONTEXT_SIZE[1]],
        "Z Context Length": ["int", -GENERATION_CONTEXT_SIZE[2]],
        "Steps": ["int", 64, 1, 256],
        "Inpaint Strength": ["str", "1.0"],
        "Endpoint": ["str", "http://localhost:8001"],
    },
}
 