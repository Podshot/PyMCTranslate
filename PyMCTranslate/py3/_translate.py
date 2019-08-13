from typing import Union, Tuple, List, Dict
try:
	from amulet.api.block import Block
except:
	from PyMCTranslate.py3.api.block import Block
import amulet_nbt
from amulet_nbt import TAG_Byte, TAG_Short, TAG_Int, TAG_Long, TAG_Float, TAG_Double, TAG_Byte_Array, TAG_String, TAG_List, TAG_Compound, TAG_Int_Array, TAG_Long_Array

from PyMCTranslate.py3.helpers.objects import BlockEntity, Entity  # TODO: switch these for more full ones in API
from PyMCTranslate.py3.helpers.nbt import from_spec
from PyMCTranslate.py3.translation_manager import SubVersion


def get_blockentity(level, location: Tuple[int, int, int]) -> BlockEntity:
	"""Reach back into the level and pull the block entity from the given location
	Should return a BlockEntity class or None if there is no BlockEntity at the given location
	"""
	if level is not None:
		return level.tileEntityAt(*location)
	else:
		raise Exception('level is None and more data needed from it')


def get_block_at(level, location: Tuple[int, int, int]) -> Tuple[Union[Block, None], Union[BlockEntity, None]]:
	"""Should return the Block instance in the input format at location"""
	return None, None


_datatype_to_nbt = {
	'byte': TAG_Byte,
	'short': TAG_Short,
	'int': TAG_Int,
	'long': TAG_Long,
	'float': TAG_Float,
	'double': TAG_Double,
	'byte_array': TAG_Byte_Array,
	'string': TAG_String,
	'list': TAG_List,
	'compound': TAG_Compound,
	'int_array': TAG_Int_Array,
	'long_array': TAG_Long_Array
}

_nbt_to_datatype = {
	'TAG_Byte': 'byte',
	'TAG_Short': 'short',
	'TAG_Int': 'int',
	'TAG_Long': 'long',
	'TAG_Float': 'float',
	'TAG_Double': 'double',
	'TAG_Byte_Array': 'byte_array',
	'TAG_String': 'string',
	'TAG_List': 'list',
	'TAG_Compound': 'compound',
	'TAG_Int_Array': 'int_array',
	'TAG_Long_Array': 'long_array'
}


def datatype_to_nbt(datatype: str) -> Union[TAG_Byte, TAG_Short, TAG_Int, TAG_Long, TAG_Float, TAG_Double, TAG_Byte_Array, TAG_String, TAG_List, TAG_Compound, TAG_Int_Array, TAG_Long_Array]:
	return _datatype_to_nbt[datatype]


def nbt_to_datatype(
	nbt: Union[TAG_Byte, TAG_Short, TAG_Int, TAG_Long, TAG_Float, TAG_Double, TAG_Byte_Array, TAG_String, TAG_List, TAG_Compound, TAG_Int_Array, TAG_Long_Array]
) -> str:
	return _nbt_to_datatype[nbt.__class__.__name__]


def index_nbt(nbt: Union[TAG_Compound, TAG_List], nbt_path: Tuple[str, str, List[Tuple[Union[str, int], str]]]):
	outer_name, outer_type, nbt_path = nbt_path
	# TODO: check the outer name
	if not isinstance(nbt, datatype_to_nbt(outer_type)):
		return None
	for path, nbt_type in nbt_path:
		if isinstance(path, int) and isinstance(nbt, TAG_List) and len(nbt) > path:
			nbt = nbt[path]
		elif isinstance(path, str) and isinstance(nbt, TAG_Compound) and path in nbt:
			nbt = nbt[path]
		else:
			return None
	return nbt


def translate(world, object_input: Union[Block, Entity], input_spec: dict, mappings: List[dict], output_version: SubVersion, location: Tuple[int, int, int] = None, extra_input: BlockEntity = None) -> Tuple[Union[Block, Entity], Union[BlockEntity, None], bool, bool]:
	"""
		A function to translate the object input to the output version

		:param world: a view into the level to access additional data
		:param object_input: the Block or Entity object to be converted
		:param input_spec: the specification for the object_input from the input block_format
		:param mappings: the mapping file for the input_object
		:param output_version: A way for the function to look at the specification being converted to. (used to load default properties)
		:param location: (x, y, z) only used for Blocks if data beyond the object_input is needed
		:param extra_input: secondary to the object_input a block entity can be given. This should only be used in the select block tool or plugins. Not compatible with location
		:return: output, extra_output, extra_needed, cacheable
			extra_needed: a bool to specify if more data is needed beyond the object_input
			cacheable: a bool to specify if the result can be cached to reduce future processing
			Block, None, bool, bool
			Block, BlockEntity, bool, bool
			Entity, None, bool, bool
	"""

	# set up for the _translate function which does the actual conversion
	if isinstance(object_input, Block):
		if 'nbt' in input_spec and location is not None:
			# if the block location in the world is defined then load the BlockEntity from the world
			extra_input = get_blockentity(world, location)
			if extra_input is None:
				# if there is no BlockEntity at location create it based off the specification
				namespace, base_name = input_spec['nbt_identifier'].split(':', 1)
				extra_input = BlockEntity(namespace, base_name, (0, 0, 0), from_spec(input_spec['nbt']))
			# if the BlockEntity is already defined in extra_input continue with that

			# if location and extra_input are both None then continue with the mapping as normal but without the BlockEntity.
			# The mappings will do as much as it can and will return the extra_needed flag as True telling the caller to find the location if possible
		block_input = object_input
		if extra_input is not None:
			assert isinstance(extra_input, BlockEntity)
			nbt_input = extra_input
		else:
			nbt_input = None

	elif isinstance(object_input, Entity):
		assert extra_input is None, 'When an Entity is the first input the extra input must be None'
		block_input = None
		nbt_input = object_input
	else:
		raise Exception

	# run the conversion
	output_name, output_type, new_data, extra_needed, cacheable = _translate(world, block_input, nbt_input, mappings, location)

	# sort out the outputs from the _translate function
	extra_output = None
	if output_type == 'block':
		# we should have a block output
		# create the block object based on output_name and new['properties']
		namespace, base_name = output_name.split(':', 1)
		spec = output_version.get_specification('block', namespace, base_name)
		properties = spec.get('defaults', {})
		for key, val in new_data['properties'].items():
			properties[key] = val
		output = Block(None, namespace, base_name, properties)

		if 'nbt' in spec:
			namespace, base_name = spec['nbt_identifier'].split(':', 1)
			extra_output = BlockEntity(namespace, base_name, (0, 0, 0), from_spec(spec['nbt']))
			# not quite sure how to handle coordinates here. I could populate it will location but this is not always given
			# it makes sense to me to have the wrapper program set the coordinates so none are missed.
			# for new_nbt in new['nbt']:
				# merge into extra_output
			# TODO: merge new['nbt'] into extra_output

	elif output_type == 'entity':
		# we should have an entity output
		# create the entity object based on output_name and new['nbt']
		namespace, base_name = output_name.split(':', 1)
		spec = output_version.get_specification('entity', namespace, base_name)
		output = Entity(namespace, base_name, (0.0, 0.0, 0.0), from_spec(spec['nbt']))
		# TODO: merge new['nbt'] into nbt_output and translate to an entity
	else:
		raise Exception
	return output, extra_output, extra_needed, cacheable


def _translate(world, block_input: Union[Block, None], nbt_input: Union[Entity, BlockEntity, None], mappings: List[dict], location: Tuple[int, int, int] = None, nbt_path: Tuple[str, str, List[Tuple[Union[str, int], str]]] = None, inherited_data: Tuple[Union[str, None], Union[str, None], dict, bool, bool] = None) -> Tuple[Union[str, None], Union[str, None], dict, bool, bool]:
	"""
	:param world:
	:param block_input:
	:param nbt_input:
	:param mappings:
	:param location:
	:param inherited_data:
	:return:
		output_name - string of the object being output
		output_type - string of the type output name is (should be 'block' or 'entity')
		new - a dictionary that looks like this {'properties': {}, 'nbt': # TODO: work out NBT}
		extra_needed - bool. Specifies if more data is needed (ie if location needs to be given to do a full map)
		cacheable - bool. Specifies if the input object is cachable. Only true for simple Blocks without BlockEntities
	"""
	if inherited_data is not None:
		output_name, output_type, new_data, extra_needed, cacheable = inherited_data
	else:
		output_name = None
		output_type = None
		new_data = {
			'properties': {},
			'nbt': []
		}  # There could be multiple 'new_block' functions in the mappings so new properties are put in here and merged at the very end
		new_data['nbt']: List[
			Tuple[
				str,
				str,
				List[
					Union[str, int], str
				],
				Union[str, int],
				Union[TAG_Byte, TAG_Short, TAG_Int, TAG_Long, TAG_Float, TAG_Double, TAG_Byte_Array, TAG_String, TAG_List, TAG_Compound, TAG_Int_Array, TAG_Long_Array]
			]
		]
		"""
		new['nbt'] = [
			[
				[
					[path0, type0],
					[path1, type1],
					...
				],
				path_n,
				NBT
			],
			...
		]
		"""
		extra_needed = False  # used to determine if extra data is required (and thus to do block by block)
		cacheable = True    # cacheable until proven otherwise

	for translate_function in mappings:
		function_name = translate_function['function']

		if 'new_block' == function_name:
			# {
			# 	"function": "new_block",
			# 	"options": "<namespace>:<base_name>"
			# }
			output_name: str = translate_function["options"]
			output_type = 'block'

		elif 'new_entity' == function_name:
			# {
			# 	"function": "new_entity",
			# 	"options": "<namespace>:<base_name>"
			# }
			output_name: str = translate_function["options"]
			output_type = 'entity'

		elif 'new_properties' == function_name:
			# {
			# 	"function": "new_properties",
			# 	"options": {
			# 		"<property_name>": "<property_value",
			# 		"<nbt_property_name>": ['snbt', "<SNBT>"]    # eg "val", "54b", "0.0d"
			# 	}
			# }
			for key, val in translate_function["options"].items():
				if isinstance(val, str):
					new_data['properties'][key] = val
				elif isinstance(val, list) and val[0] == 'snbt':
					new_data['properties'][key] = amulet_nbt.from_snbt(val[1])

		elif 'carry_properties' == function_name:
			# {
			# 	"function": "carry_properties",
			# 	"options": {
			# 		"<property_name>": ["<property_value"],
			# 		"<nbt_property_name>": ['<SNBT>']
			# 	}
			# }
			assert isinstance(block_input, Block), 'The block input is not a block'
			for key in translate_function["options"]:
				if key in block_input.properties:
					val = block_input.properties[key]
					if isinstance(val, str):
						hash_val = val
					elif isinstance(val, (TAG_Byte, TAG_Short, TAG_Int, TAG_Long, TAG_Float, TAG_Double, TAG_Byte_Array, TAG_String, TAG_List, TAG_Compound, TAG_Int_Array, TAG_Long_Array)):
						hash_val = val.to_snbt()
					else:
						continue
					if hash_val in translate_function["options"][key]:
						new_data['properties'][key] = val

		elif 'map_properties' == function_name:
			# {
			# 	"function": "map_properties",
			# 	"options": {
			# 		"<property_name>": {
			# 			"<property_value": [
			# 				<functions>
			# 			]
			# 		},
			# 		"<nbt_property_name>": {
			# 			'TAG_String("<property_value>")': [
			# 				<functions>
			# 			]
			# 		}
			# 	}
			# }
			assert isinstance(block_input, Block), 'The block input is not a block'
			for key in translate_function["options"]:
				if key in block_input.properties:
					val = str(block_input.properties[key])
					if val in translate_function["options"][key]:
						output_name, output_type, new_data, extra_needed, cacheable = _translate(world, block_input, nbt_input, translate_function["options"][key][val], location, nbt_path, (output_name, output_type, new_data, extra_needed, cacheable))

		elif 'multiblock' == function_name:
			# {
			# 	"function": "multiblock",
			# 	"options": [
			# 		{
			# 			"coords": [dx, dy, dz],
			# 			"functions": <functions>
			# 		}
			# 	]
			# }
			cacheable = False
			if location is None:
				extra_needed = True
			else:
				multiblocks = translate_function["options"]
				if isinstance(multiblocks, dict):
					multiblocks = [multiblocks]
				for multiblock in multiblocks:
					dx, dy, dz = multiblock['coords']
					x, y, z = location
					block_input_, nbt_input_ = get_block_at(world, (x + dx, y + dy, z + dz))
					output_name, output_type, new_data, extra_needed, cacheable = _translate(world, block_input_, nbt_input_, multiblock['functions'], (x + dx, y + dy, z + dz), nbt_path, (output_name, output_type, new_data, extra_needed, cacheable))

		elif 'map_block_name' == function_name:
			# {
			# 	"function": "map_block_name",
			# 	"options": {
			# 		"<namespace>:<base_name>": [
			# 			<functions>
			# 		]
			# 	}
			# }
			assert isinstance(block_input, Block), 'The block input is not a block'
			block_name = f'{block_input.namespace}:{block_input.base_name}'
			if block_name in translate_function["options"]:
				output_name, output_type, new_data, extra_needed, cacheable = _translate(world, block_input, nbt_input, translate_function["options"][block_name], location, nbt_path, (output_name, output_type, new_data, extra_needed, cacheable))

		elif 'map_input_nbt' == function_name:
			# This is a special function unlike the others. See _convert_map_input_nbt for more information
			# {
			# 	"function": "map_input_nbt",
			#   "outer_name": "",  # defaults to this if undefined
			# 	"options": {
			# 		"type": "<nbt type>",  # check that the nbt is of this type
			# 		"self_default": [],  # if the type is different run these functions : defaults to [{"function": "carry_nbt"}] which carries everything
			# 	    "functions": [],  # functions to run if defined
			#
			# 		"keys": {  # only for compound type
			# 	        str: {nested options format}
			# 		},
			#       "index": {  # only for list or array types
			# 	        str(<int>): {nested options format}     (type should not be defined for nested array types)
			# 	    },
			# 	    "nested_default": []  # only for compound, list or array types.
			# 	        If nested key/index is not in respective dictionary run these functions on them.
			#           If undefined defaults to [{"function": "carry_nbt"}] which carries everything
			# 	}
			# }
			cacheable = False
			if nbt_input is None:
				extra_needed = True
			else:
				output_name, output_type, new_data, extra_needed, cacheable = _convert_map_input_nbt(world, block_input, nbt_input, translate_function["options"], location, nbt_path, (output_name, output_type, new_data, extra_needed, cacheable))

		elif 'new_nbt' == function_name:
			# when used outside map_input_nbt
			# {
			# 	"function": "new_nbt",
			# 	"options": [
			# 		{
			#           "outer_name": "",  # defaults to this if undefined
			#           "outer_type": "compound",  # defaults to this if undefined
			# 			"path": [ # optional. Defaults to the root
			# 				[ < path1 >: Union[str, int], < datatype1 >: str]
			# 			]
			# 			"key": <key>: str or int,
			# 			"value": "<SNBT>"
			# 		}
			# 	]
			# }

			# when used inside map_input_nbt
			# {
			# 	"function": "new_nbt",
			# 	"options": [
			# 		{
			#           "outer_name": "",  # defaults to this if undefined
			#           "outer_type": "compound",  # defaults to this if undefined
			# 			"path": [ # optional. [] to be the root, undefined to be the input path
			# 				[ < path1 >: Union[str, int], < datatype1 >: str]
			# 			]
			# 			"key": <key>: Union[str, int],
			# 			"value": "<SNBT>"
			# 		}
			# 	]
			# }

			new_nbts = translate_function["options"]
			if isinstance(new_nbts, dict):
				new_nbts = [new_nbts]

			for new_nbt in new_nbts:
				if 'path' in new_nbt:
					path = new_nbt['path']
				elif nbt_path is None:
					path = []
				else:
					path = nbt_path[2]

				outer_name = new_nbt.get('outer_name', '')
				outer_type = new_nbt.get('outer_type', 'compound')

				new_data['nbt'].append((outer_name, outer_type, path, new_nbt['key'], amulet_nbt.from_snbt(new_nbt['value'])))

		elif 'carry_nbt' == function_name:
			# only works within map_input_nbt
			# {
			# 	"function": "carry_nbt",
			# 	"options": {
			# 		"outer_name": "",  # defaults to this if undefined
			# 		"outer_type": "compound",  # defaults to this if undefined
			# 		"path": [  # [] to be the root, undefined to be the input path
			# 			[ <path1>: Union[str, int], <datatype1>: str],
			# 			...
			# 		],
			# 		"key": <key>: Union[str, int]  # undefined to remain under the same key/index
			# 		"type": <type>: str  # undefined to remain as the input type
			# 	}
			# }
			cacheable = False
			if nbt_input is None:
				extra_needed = True
			elif nbt_path is not None:
				nbt = index_nbt(nbt_input.nbt, nbt_path)
				if nbt is None:
					raise Exception('This code should not be run because it should be caught by other code before it gets here.')
				val = nbt.value

				options = translate_function.get('options', {})
				outer_name = options.get('outer_name', '')
				outer_type = options.get('outer_type', 'compound')
				path = options.get('path', nbt_path[2][:-1])
				key = options.get('key', nbt_path[2][-1][0])
				nbt_type = options.get('type', nbt_path[2][-1][1])

				# TODO: some kind of check to make sure that the input data type nbt_path[-1][1] can be cast to nbt_type
					# perhaps this should be done in the compiler rather than at runtime
				new_data['nbt'].append((outer_name, outer_type, path, key, datatype_to_nbt(nbt_type)(val)))

		elif 'map_nbt' == function_name:
			# "map_nbt": {  # based on the input nbt value at path (should only be used with end stringable datatypes)
			# 	"cases": {}  # if the data is in here then do the nested functions
			# 	"default": {},  # if the data is not in cases or cases is not defined then do these functions
			# }
			cacheable = False
			if nbt_input is None:
				extra_needed = True
			elif nbt_path is not None:
				run_default = True
				if 'cases' in translate_function["options"]:
					nbt = index_nbt(nbt_input.nbt, nbt_path)
					nbt_hash = nbt.to_snbt()
					if nbt_hash in translate_function["options"]['cases']:
						output_name, output_type, new_data, extra_needed, cacheable = _translate(world, block_input, nbt_input, translate_function["options"]['cases'][nbt_hash], location, nbt_path, (output_name, output_type, new_data, extra_needed, cacheable))
						run_default = False

				if run_default:
					output_name, output_type, new_data, extra_needed, cacheable = _translate(world, block_input, nbt_input, translate_function["options"].get('default', {}), location, nbt_path, (output_name, output_type, new_data, extra_needed, cacheable))

	return output_name, output_type, new_data, extra_needed, cacheable


def _convert_map_input_nbt(level, block_input: Union[Block, None], nbt_input: Union[Entity, BlockEntity, None], mappings: dict, location: Tuple[int, int, int] = None, nbt_path: Tuple[str, str, List[Tuple[Union[str, int], str]]] = None, inherited_data: Tuple[Union[str, None], Union[str, None], dict, bool, bool] = None) -> Tuple[Union[str, None], Union[str, None], dict, bool, bool]:
	if nbt_path is None:
		nbt_path = ('', 'compound', [])
	if inherited_data is not None:
		output_name, output_type, new_data, extra_needed, cacheable = inherited_data
	else:
		output_name = None
		output_type = None
		new_data = {
			'properties': {},
			'nbt': []
		}  # There could be multiple 'new_block' functions in the mappings so new properties are put in here and merged at the very end
		new_data['nbt']: List[
			List[
				str,
				str,
				List[
					Union[str, int], str
				],
				Union[str, int],
				Union[TAG_Byte, TAG_Short, TAG_Int, TAG_Long, TAG_Float, TAG_Double, TAG_Byte_Array, TAG_String, TAG_List, TAG_Compound, TAG_Int_Array, TAG_Long_Array]
			]
		]
		"""
		new['nbt'] = [
			[
				[
					[path0, type0],
					[path1, type1],
					...
				],
				path_n,
				NBT
			],
			...
		]
		"""
		extra_needed = False  # used to determine if extra data is required (and thus to do block by block)
		cacheable = True    # cacheable until proven otherwise

	nbt = index_nbt(nbt_input.nbt, nbt_path)  # nbt_path should always exist in nbt_input.nbt because the calling code should check that

	datatype = mappings['type']

	if 'functions' in mappings:
		# run functions if present
		output_name, output_type, new_data, extra_needed, cacheable = _translate(level, block_input, nbt_input, mappings['functions'], location, nbt_path, (output_name, output_type, new_data, extra_needed, cacheable))

	if isinstance(nbt, datatype_to_nbt(datatype)):
		# datatypes match
		if datatype == 'compound':
			for key in nbt.value:
				if key in mappings.get('keys', {}):
					output_name, output_type, new_data, extra_needed, cacheable = _convert_map_input_nbt(level, block_input, nbt_input, mappings['keys'][key], location, (nbt_path[0], nbt_path[1], nbt_path[2] + [(key, nbt_to_datatype(nbt.value[key]))]), (output_name, output_type, new_data, extra_needed, cacheable))
				else:
					output_name, output_type, new_data, extra_needed, cacheable = _translate(level, block_input, nbt_input, mappings.get('nested_default', [{"function": "carry_nbt"}]), location, (nbt_path[0], nbt_path[1], nbt_path[2] + [(key, nbt_to_datatype(nbt.value[key]))]), (output_name, output_type, new_data, extra_needed, cacheable))

		elif datatype == 'list':
			for index in range(len(nbt)):
				if str(index) in mappings.get('index', {}):
					output_name, output_type, new_data, extra_needed, cacheable = _convert_map_input_nbt(level, block_input, nbt_input, mappings['index'][str(index)], location, (nbt_path[0], nbt_path[1], nbt_path[2] + [(index, nbt_to_datatype(nbt.value[index]))]), (output_name, output_type, new_data, extra_needed, cacheable))
				else:
					output_name, output_type, new_data, extra_needed, cacheable = _translate(level, block_input, nbt_input, mappings.get('nested_default', [{"function": "carry_nbt"}]), location, (nbt_path[0], nbt_path[1], nbt_path[2] + [(index, nbt_to_datatype(nbt.value[index]))]), (output_name, output_type, new_data, extra_needed, cacheable))

		# elif datatype in ('byte', 'short', 'int', 'long', 'float', 'double', 'string'):
		# 	pass

		elif datatype in ('byte_array', 'int_array', 'long_array'):
			nested_datatype = datatype.replace('_array', '')
			for index in range(len(nbt)):
				if str(index) in mappings.get('index', {}):
					output_name, output_type, new_data, extra_needed, cacheable = _convert_map_input_nbt(level, block_input, nbt_input, mappings['index'][str(index)], location, (nbt_path[0], nbt_path[1], nbt_path[2] + [(index, nested_datatype)]), (output_name, output_type, new_data, extra_needed, cacheable))
				else:
					output_name, output_type, new_data, extra_needed, cacheable = _translate(level, block_input, nbt_input, mappings.get('nested_default', [{"function": "carry_nbt"}]), location, (nbt_path[0], nbt_path[1], nbt_path[2] + [(index, nested_datatype)]), (output_name, output_type, new_data, extra_needed, cacheable))

	else:
		# datatypes do not match. Run self_default
		output_name, output_type, new_data, extra_needed, cacheable = _translate(level, block_input, nbt_input, mappings.get('self_default', [{"function": "carry_nbt"}]), location, nbt_path, (output_name, output_type, new_data, extra_needed, cacheable))

	return output_name, output_type, new_data, extra_needed, cacheable
