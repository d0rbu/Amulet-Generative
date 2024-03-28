# Generate operation

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

from amulet_map_editor.programs.edit.api.operations.errors import (
    OperationError,
)


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

GENERATION_SIZE = (16, 16, 16)
GENERATION_CONTEXT_SIZE = (8, 8, 8)
TUBE_LENGTH = 8
EMPTY_BLOCK = Block.from_string_blockstate("minecraft:air")

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
    generation_size = np.array(generation_size)
    generation_context_size = np.array(generation_context_size)
    generated_size = generation_size - generation_context_size

    total_context_offset = (
        options["X Context Length"],
        options["Y Context Length"],
        options["Z Context Length"],
    )
    total_context_offset = np.array(total_context_offset)
    total_context_direction = (total_context_offset >= 0).astype(int) * 2 - 1
    total_context_size = np.stack([np.abs(total_context_offset), generation_size - 1], axis=0).min(axis=0)  # ensure we can generate something
    initial_generated_size = generation_size - total_context_size

    contiguous_groups = contiguous_selections(selection)

    boxes: list[SelectionBox] = []
    for group in contiguous_groups:
        bottom_corner = np.array(group.min)
        top_corner = np.array(group.max)
        np_space = np.zeros((top_corner - bottom_corner), dtype=bool)  # origin at bottom corner

        # Set True to values inside of groups
        for selection in group:
            point_min = selection.min - bottom_corner
            point_max = selection.max - bottom_corner
            np_space[point_min[0]:point_max[0], point_min[1]:point_max[1], point_min[2]:point_max[2]] = True

        while np.any(np_space):
            non_zero_points = np.roll(np.array(np_space.nonzero()), -1, axis=0)  # (3, n) array of non-zero points (y z x order)
            # Exit if there are no more non-zero points
            if non_zero_points.size == 0:
                break

            smallest_non_zero_point = np.lexsort(non_zero_points)[0]

            # Calculate the opposite corner of the volume (has overhanging points)
            starting_corner = np.roll(non_zero_points[:, smallest_non_zero_point], 1)  # (x, y, z) order

            generated_size_for_this_box = generated_size
            generation_context_size_for_this_box = generation_context_size

            if np.any(starting_corner == 0):
                # If the starting corner is at the starting edge of the volume
                # use the initial_generated_size
                generated_size_for_this_box = initial_generated_size
                generation_context_size_for_this_box = total_context_size

            opposite_corner = starting_corner + generated_size_for_this_box

            # Create a new volume and add it to the list
            boxes.append((
                SelectionBox(starting_corner + bottom_corner - generation_context_size_for_this_box, opposite_corner + bottom_corner),
                generation_context_size_for_this_box,
            ))

            # Set the covered area to 0 in the np_space
            np_space[starting_corner[0]:opposite_corner[0], starting_corner[1]:opposite_corner[1], starting_corner[2]:opposite_corner[2]] = False

    return boxes

def operation(
    world: BaseLevel, dimension: Dimension, selection: SelectionGroup, options: dict
) -> Generator[float, None, None]:
    structure_block_type = options["Structure Block Type"]
    structure_block = Block.from_string_blockstate(f"minecraft:{structure_block_type}")

    # When the user presses the run button this function will be run as normal but
    # since the "options" key was defined in export this function will get another
    # input in the form of a dictionary where the keys are the same as you defined
    # them in the options dictionary above and the values are what the user picked
    # in the UI (bool, int, float, str)
    # If "options" is not defined in export this will just be an empty dictionary
    generate_boxes = create_generate_boxes(world, dimension, selection, options)

    endpoint = options["Endpoint"]
    endpoint = f"{endpoint}/structure"

    for i, (box, box_generation_context_size) in enumerate(generate_boxes):
        block_coords = [
            (x, y, z)
            for y, z, x in product(
                range(box.min_y, box.max_y),
                range(box.min_z, box.max_z),
                range(box.min_x, box.max_x),
            )
        ]

        blocks = [world.get_block(x, y, z, dimension) for x, y, z in block_coords]
        structure = [block_to_solid(block) for block in blocks]

        del blocks, block_coords

        structure = np.array(structure, dtype=np.int8).reshape(GENERATION_SIZE[1], GENERATION_SIZE[2], GENERATION_SIZE[0])  # (y, z, x) order
        structure[box_generation_context_size[1]:, box_generation_context_size[2]:, box_generation_context_size[0]:] = -1  # set the context to -1
        structure = structure.reshape(-1, TUBE_LENGTH).tolist()  # (y * z * x, tube_length)

        structure = [
            [
                is_solid if is_solid != -1 else None
                for is_solid in tube
            ]
            for tube in structure
        ]

        generated_tube_indices = [i for i, tube in enumerate(structure) if None in tube]

        strategy = {
            "strategy": options["Sampling Strategy"],
        }

        if strategy["strategy"] == "topk":
            strategy["k"] = options["Top K"]
        elif strategy["strategy"] == "nucleus":
            strategy["p"] = float(options["Top P"])

        data = {
            "data": structure,
            "y": 0,
            "sampling": strategy,
        }

        stream_response = requests.post(endpoint, json=data, stream=True)
        stream_response_iter = stream_response.iter_lines()

        finished = False
        for j, tube_idx in enumerate(generated_tube_indices):
            if not finished:
                try:
                    tube = next(stream_response_iter)
                except StopIteration:
                    finished = True

            yield (i + j / len(generated_tube_indices)) / len(generate_boxes)

            generated_tube = json.loads(tube)[0]
            generated_coordinates = tube_idx_to_coordinates(box, tube_idx)

            for coordinates, solid in zip(generated_coordinates, generated_tube):
                if solid == -1:
                    finished = True

                if coordinates in selection:
                    world.set_version_block(
                        coordinates[0],
                        coordinates[1],
                        coordinates[2],
                        dimension,
                        version = ("java", (1, 16, 2)),
                        block = structure_block if solid == 1 and not finished else EMPTY_BLOCK,
                    )

def tube_idx_to_coordinates(box: SelectionBox, tube_idx: int, generation_size: BlockCoordinates = GENERATION_SIZE, tube_length: int = TUBE_LENGTH) -> BlockCoordinatesNDArray:
    # make np array where each element is its own coordinates
    coordinates_array = np.array(list(product(range(generation_size[1]), range(generation_size[2]), range(generation_size[0]))))
    coordinates_array = coordinates_array.reshape(-1, tube_length, 3)

    tube = np.roll(coordinates_array[tube_idx], 1, axis=-1)  # (tube_length, 3) array of coordinates

    return tube + np.array([[box.min_x, box.min_y, box.min_z]])

def block_to_solid(block: Block) -> int:
    name = block.base_name

    return name != "air"

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
    assert generate_boxes[1].min == (-2, 0, -2)
    assert generate_boxes[1].max == (2, 4, 2)
    assert generate_boxes[2].min == (-2, -2, 0)
    assert generate_boxes[2].max == (2, 2, 4)
    assert generate_boxes[3].min == (-2, 0, 0)
    assert generate_boxes[3].max == (2, 4, 4)
    assert generate_boxes[4].min == (0, -2, -2)
    assert generate_boxes[4].max == (4, 2, 2)
    assert generate_boxes[5].min == (0, 0, -2)
    assert generate_boxes[5].max == (4, 4, 2)
    assert generate_boxes[6].min == (0, -2, 0)
    assert generate_boxes[6].max == (4, 2, 4)
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
    assert len(generate_boxes) == 6
    assert generate_boxes[0].min == (-2, -2, -2)
    assert generate_boxes[0].max == (2, 2, 2)
    assert generate_boxes[1].min == (-1, 0, -1)
    assert generate_boxes[1].max == (3, 4, 3)
    assert generate_boxes[2].min == (-1, -1, 0)
    assert generate_boxes[2].max == (3, 3, 4)
    assert generate_boxes[3].min == (0, -1, -1)
    assert generate_boxes[3].max == (4, 3, 3)
    assert generate_boxes[4].min == (2, 2, 2)
    assert generate_boxes[4].max == (6, 6, 6)
    assert generate_boxes[5].min == (5, 5, 5)
    assert generate_boxes[5].max == (9, 9, 9)

####### END TESTS #######

export = {
    "name": "Structure Generative Fill",
    "operation": operation,
    "options": {
        "X Context Length": ["int", -GENERATION_CONTEXT_SIZE[0]],
        "Y Context Length": ["int", -GENERATION_CONTEXT_SIZE[1]],
        "Z Context Length": ["int", -GENERATION_CONTEXT_SIZE[2]],
        "Structure Block Type": ["str", "oak_planks"],
        "Sampling Strategy": ["str_choice", "sample", "greedy", "topk", "nucleus"],
        "Top K": ["int", 8, 1, 256],
        "Top P": ["str", "0.9"],
        "Endpoint": ["str", "http://localhost:8001"],
    },
}
