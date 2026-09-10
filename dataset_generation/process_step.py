import json
import os
import sys


if len(sys.argv) < 2:
    raise RuntimeError("Expected the path to a STEP file.")

step_path = os.path.abspath(sys.argv[-1])

if not os.path.isfile(step_path):
    raise RuntimeError(
        "STEP file does not exist: {}".format(step_path)
    )


sample_dir = os.path.dirname(step_path)
sample_name = os.path.splitext(os.path.basename(step_path))[0]


# Expected structure:
# root/datasets/dataset_name/split/sample/sample.step
split_dir = os.path.dirname(sample_dir)
dataset_path = os.path.dirname(split_dir)
datasets_dir = os.path.dirname(dataset_path)
project_root = os.path.dirname(datasets_dir)

script_dir = os.path.join(
    project_root,
    "dataset_generation",
)

config_path = os.path.join(
    script_dir,
    "dataset_config.json",
)


with open(config_path, "r") as config_file:
    config = json.load(config_file)


cae_path = os.path.join(
    sample_dir,
    sample_name + ".cae",
)

inp_path = os.path.join(
    sample_dir,
    sample_name + ".inp",
)

am_modeler_path = config["am_modeler_path"]

if am_modeler_path not in sys.path:
    sys.path.append(am_modeler_path)

if script_dir not in sys.path:
    sys.path.insert(0, script_dir)


from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup

from customKernel import *
from amModule import *

import amKernelInit
import amModule
import customKernel

from process_step_functions import (
    horizontal_faces,
    estimate_time_period,
    part_bbox,
    replace_between_markers,
)


install()
executeOnCaeStartup()

baseplate_seed_size = config["baseplate_seed_size"]
baseplate_thickness = config["baseplate_thickness"]
part_seed_size = config["part_seed_size"]

print_margin = config["print_margin"]
slice_height = config["slice_height"]
time_buffer = config["time_buffer"]

laser_power = config["laser_power"]
hatch_spacing = config["hatch_spacing"]
scan_speed = config["scan_speed"]
on_time_fraction = config["on_time_fraction"]
rotation_angle = config["rotation_angle"]

baseplate_temperature = config["baseplate_initial_temperature"]
powder_temperature = config["part_initial_temperature"]


initial_increment = 1.0
minimum_increment = 1e-5
maximum_increment = 10.0
maximum_number_of_increments = 10000
maximum_temperature_change = 10000.0



Mdb() # Create a new model database

model = mdb.models["Model-1"]
mdb.models['Model-1'].setValues(absoluteZero=-273.15, stefanBoltzmann=5.67E-11)

#Define Material; in this case Ti6Al4V as defined in the PBF tutorial

mdb.models['Model-1'].Material(name='Ti6Al4V')
mdb.models['Model-1'].materials['Ti6Al4V'].Conductivity(
    temperatureDependency=ON, table=((7.02, 25.5), (7.5, 99.0), (9.75, 267.0), 
    (11.8, 433.0), (14.2, 599.0), (17.1, 764.0), (21.0, 930.0), (22.6, 994.0), 
    (21.1, 1097.0), (23.4, 1261.0), (27.0, 1596.0), (32.5, 1681.0), (34.6, 
    1697.0)))
mdb.models['Model-1'].materials['Ti6Al4V'].LatentHeat(table=((411000000000.0, 
    1550.0, 1600.0), ))

mdb.models['Model-1'].materials['Ti6Al4V'].Density(temperatureDependency=ON, 
    table=((4.42e-09, 20.0), (4.41e-09, 101.5), (4.39e-09, 272.3), (4.36e-09, 
    443.1), (4.34e-09, 613.9), (4.31e-09, 784.7), (4.29e-09, 955.4), (4.26e-09, 
    1126.2), (4.24e-09, 1297.0), (4.21e-09, 1467.8), (4.2e-09, 1598.1), (
    4.19e-09, 1649.3), (4.06e-09, 1672.1)))
mdb.models['Model-1'].materials['Ti6Al4V'].SpecificHeat(
    temperatureDependency=ON, table=((546000000.0, 22.9), (564000000.0, 104.3), 
    (601000000.0, 272.3), (639000000.0, 440.4), (675000000.0, 608.4), (
    710000000.0, 776.5), (754000000.0, 992.3), (661000000.0, 1096.7), (
    673000000.0, 1165.9), (703000000.0, 1336.7), (733000000.0, 1504.7), (
    759000000.0, 1648.5)))

#Define meshes

elem_type_hex = mesh.ElemType(elemCode=DC3D8, elemLibrary = STANDARD)
elem_type_wedge = mesh.ElemType(elemCode=DC3D6, elemLibrary = STANDARD) #this elem type and the next are not used, but were output by abaqus. kept for compatibility
elem_type_tet = mesh.ElemType(elemCode=DC3D4, elemLibrary = STANDARD)

s1 = mdb.models['Model-1'].ConstrainedSketch(name='__profile__', 
    sheetSize=300.0)
g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
s1.setPrimaryObject(option=STANDALONE)
s1.rectangle(point1=(139.0, 139.0), point2=(-139.0, -139.0))
s1.FilletByRadius(radius=24.0, curve1=g[5], nearPoint1=(-120.001045227051, 
    138.688888549805), curve2=g[4], nearPoint2=(-139.477722167969, 
    118.430618286133))
s1.FilletByRadius(radius=24.0, curve1=g[2], nearPoint1=(139.282424926758, 
    101.008499145508), curve2=g[5], nearPoint2=(119.399940490723, 
    137.87858581543))

s1.FilletByRadius(radius=24.0, curve1=g[3], nearPoint1=(71.0877990722656, 
    -137.287734985352), curve2=g[2], nearPoint2=(139.778045654297, 
    -81.4005432128906))
s1.FilletByRadius(radius=24.0, curve1=g[4], nearPoint1=(-138.162933349609, 
    -52.8218421936035), curve2=g[3], nearPoint2=(-93.6415405273438, 
    -137.922805786133))
baseplate = mdb.models['Model-1'].Part(name='Baseplate', dimensionality=THREE_D, 
    type=DEFORMABLE_BODY)

baseplate.BaseSolidExtrude(sketch=s1, depth=baseplate_thickness)

c = baseplate.cells
baseplate_cells = c.getSequenceFromMask(mask=('[#1 ]', ), )
baseplate.Set(cells=baseplate_cells, name='BaseplateGeometry')
baseplate_pickedRegions =(baseplate_cells, )

mdb.models['Model-1'].HomogeneousSolidSection(name='Ti6Al4V', 
    material='Ti6Al4V', thickness=None)

BaseplateGeometry = baseplate.sets['BaseplateGeometry']

baseplate.SectionAssignment(region= BaseplateGeometry, sectionName='Ti6Al4V', offset=0.0, 
    offsetType=MIDDLE_SURFACE, offsetField='', 
    thicknessAssignment=FROM_SECTION)

baseplate.setElementType(regions=baseplate_pickedRegions, elemTypes=(elem_type_hex, elem_type_wedge, 
    elem_type_tet))

baseplate.seedPart(size=baseplate_seed_size, deviationFactor=0.1, minSizeFactor=0.1)

baseplate.generateMesh()





#define geometry of AMPart
step = mdb.openStep(step_path, 
    scaleFromFile=OFF)  #Open the STEP file

part = model.PartFromGeometryFile(name=sample_name, geometryFile=step, 
    combine=False, dimensionality=THREE_D, type=DEFORMABLE_BODY)

c = part.cells
part_cells = c.getSequenceFromMask(mask=('[#1 ]', ), )
part.Set(cells=part_cells, name='AMPartGeometry')
part_pickedRegions =(part_cells, )

part_region = part.sets['AMPartGeometry']

part.SectionAssignment(region= part_region, sectionName='Ti6Al4V', offset=0.0, 
    offsetType=MIDDLE_SURFACE, offsetField='', 
    thicknessAssignment=FROM_SECTION)


part.seedPart(size= part_seed_size, deviationFactor=0.1, minSizeFactor=0.1)

part.setElementType(regions=part_pickedRegions, elemTypes=(elem_type_hex, elem_type_wedge, 
    elem_type_tet))

part.setMeshControls(regions= part.cells[:], elemShape=TET, technique=FREE)

part.generateMesh()
print("AM part cells:", len(part.cells))
print("AM part nodes:", len(part.nodes))
print("AM part elements:", len(part.elements))

if len(part.elements) == 0:
    raise RuntimeError(
        "Meshing failed: AM part contains no elements."
    )

#Define instances
a = mdb.models['Model-1'].rootAssembly
a.Instance(name='AMPart-1', part=part, dependent=ON)
a.Instance(name='Baseplate-1', part=baseplate, dependent=ON)

part_bottom_z = min(vertex.pointOn[0][2] for vertex in part.vertices)

z_shift = baseplate_thickness - part_bottom_z

a.translate(instanceList=('AMPart-1', ), vector=(0.0, 0.0, z_shift)) #align bottom of AM part with top of baseplate

#define instance surfaces
s1 = a.instances['Baseplate-1'].faces
side1Faces1 = s1.getSequenceFromMask(mask=('[#200 ]', ), )
a.Surface(side1Faces=side1Faces1, name='Baseplate_Bottom')
side1Faces1 = s1.getSequenceFromMask(mask=('[#100 ]', ), )
a.Surface(side1Faces=side1Faces1, name='Baseplate_Top')

part_instance = a.instances["AMPart-1"]
bottom_face = min(horizontal_faces(part_instance), key = lambda item: item[1])[0]
 #NOTE: this assumes a single plane of contact between baseplate and part. Will break if not changed on more complex geometries

bottom_face_sequence = part_instance.faces[bottom_face.index : bottom_face.index +1]

a.Surface(side1Faces=bottom_face_sequence, name="AMPart_Bottom")

#Define thermal step
bbox = part_bbox(part)

xmin, ymin, zmin = bbox["low"]
xmax, ymax, zmax = bbox["high"]

width_x = xmax - xmin
width_y = ymax - ymin
height = zmax - zmin

patch_x  = width_x + print_margin
patch_y  = width_y + print_margin

total_time = (
    1.0 + time_buffer
) * estimate_time_period(
    height,
    patch_x,
    patch_y,
    layer_height=slice_height,
    hatch_spacing=hatch_spacing,
    scan_speed=scan_speed,
    on_time_frac=on_time_fraction,
)

a.translate(instanceList=("AMPart-1",), vector = (-xmin, -ymin, 0)) # Move part so that x, y > 0 so the pattern-based scan pattern stops throwing a fit

mdb.models["Model-1"].HeatTransferStep(
    name="LPBF_thermal",
    previous="Initial",
    timePeriod=total_time,
    maxNumInc=maximum_number_of_increments,
    initialInc=initial_increment,
    minInc=minimum_increment,
    maxInc=maximum_increment,
    deltmx=maximum_temperature_change,
)


#Define boundary conditions and constraints
mdb.models['Model-1'].Tie(name='Tie_AMPart_Baseplate', master=a.surfaces["Baseplate_Top"], 
    slave=a.surfaces["AMPart_Bottom"], positionToleranceMethod=COMPUTED, adjust=ON, 
    tieRotations=ON, thickness=ON)

mdb.models['Model-1'].FilmCondition(name='BaseplateBottomFlux', 
    createStepName='LPBF_thermal', surface=a.surfaces["Baseplate_Bottom"], definition=EMBEDDED_COEFF, 
    filmCoeff=0.06, filmCoeffAmplitude='', sinkTemperature=baseplate_temperature, 
    sinkAmplitude='', sinkDistributionType=UNIFORM, sinkFieldName='')

mdb.models['Model-1'].Temperature(name='Predefined Field-1', 
    createStepName='Initial', region= a.instances['Baseplate-1'].sets['BaseplateGeometry'], distributionType=UNIFORM, 
    crossSectionDistribution=CONSTANT_THROUGH_THICKNESS, magnitudes=(baseplate_temperature, ))

mdb.models['Model-1'].Temperature(name='Predefined Field-2', 
    createStepName='Initial', region=a.instances['AMPart-1'].sets['AMPartGeometry'], distributionType=UNIFORM, 
    crossSectionDistribution=CONSTANT_THROUGH_THICKNESS, magnitudes=(powder_temperature, ))


amModule.createAMModel(amModelName='AM-Model-1', modelName1='Model-1', 
    stepName1='LPBF_thermal', analysisType1=HEAT_TRANSFER, isSequential=OFF, 
    modelName2='', stepName2='', analysisType2=STRUCTURAL, 
    processType=AMPROC_ABAQUS_BUILTIN)
mdb.customData.am.amModels['AM-Model-1'].addParameterTableType(
    parameterTableTypeName='"ABQ_AM.MaterialDeposition.Advanced"', 
    parameterTableTypeTable=(('ENUM', '"Activation Type"', 'Full|Partial', 
    'Partial'), ('FLOAT', '"Activation Threshold"', '', '0.0'), ('FLOAT', 
    '"Max Volume fraction"', '', '1.0'), ('FLOAT', 
    '"Max Volume FractionThreshold for Full Activation"', '', '0'), ('STRING', 
    '"Update Orientation"', 'Generic', 'Yes'), ('INTEGER', 
    '"Element Subdivision Order"', '', '0')))





part.Set(name = "PRINT_PART_TEST", elements = part.elements[:])

mdb.saveAs(pathName= cae_path)

os.chdir(sample_dir)


#Make .inp file
mdb.Job(name=sample_name, model='Model-1', description='LPBF thermal model', 
    type=ANALYSIS, atTime=None, waitMinutes=0, waitHours=0, queue=None, 
    memory=90, memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True, 
    explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF, 
    modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine='', 
    scratch='', resultsFormat=ODB, multiprocessingMode=DEFAULT, numCpus=1, 
    numGPUs=0)

mdb.jobs[sample_name].writeInput(consistencyChecking=OFF)

#import and process .inp file
with open(inp_path, 'r') as inp_file:
    lines = inp_file.readlines()

start_marker1 = "**--------Table Types Defined in the Abaqus AM-Interface------"
end_marker1 = "**-----Table Collections defined in the Abaqus AM-Interface---"
start_marker2 = "** STEP: LPBF_thermal"
end_marker2 = "** INTERACTIONS"
insert_marker = "AMPart_Bottom, Baseplate_Top"


new_content = ["""*PROPERTY TABLE TYPE, NAME = "ABQ_AM.AbsorptionCoeff" , PROPERTIES = 1
"AbsorptionCoeff", Unitless
*PROPERTY TABLE TYPE, NAME = "ABQ_AM.EnclosureAmbientTemp" , PROPERTIES = 1
"VATTemperature", 
*PARAMETER TABLE TYPE,  NAME="ABQ_AM.ScanParameter.Define",  PARAMETERS = 4
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
*PARAMETER TABLE TYPE,  NAME="ABQ_AM.ThermoMech.Activation.Advanced",  PARAMETERS = 4
STRING, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
*PARAMETER TABLE TYPE,  NAME="ABQ_AM.ThermoMech.PatternBased.Activation",  PARAMETERS = 13
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
STRING, , , 
*PARAMETER TABLE TYPE,  NAME="ABQ_AM.ThermoMech.PatternBased.Advanced",  PARAMETERS = 2
STRING, , , 
INTEGER, , , 
*PARAMETER TABLE TYPE,  NAME="ABQ_AM.ThermoMech.PatternBased.Define",  PARAMETERS = 6
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
STRING, , , 
FLOAT, , , 
*PARAMETER TABLE TYPE,  NAME="ABQ_AM.ThermoMech.PatternBased.ScanStrategies",  PARAMETERS = 1
STRING, , , 
*PARAMETER TABLE TYPE,  NAME="ABQ_AM.ThermoMech.PatternBased.ScanStrategy.Define",  PARAMETERS = 8
STRING, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
FLOAT, , , 
*PARAMETER TABLE TYPE,  NAME="ABQ_AM.ThermoMech.PatternParameters",  PARAMETERS = 1
STRING, , , 
**------------------------------------------------------------
**-----Table Collections defined in the Abaqus AM-Interface---
**------------------------------------------------------------

*TABLE COLLECTION, NAME="ABQ_TMP.ThermalPatternActivation"
**-------------------
*PARAMETER TABLE,  TYPE="ABQ_AM.ThermoMech.Activation.Advanced"
**Full/Partial,	min. vol. activation threshold, max. vol. activation threshold, vol. activation threshold "full" mode
  "Partial", 	0., 	1., 	0.,
**-------------------
*PARAMETER TABLE,  TYPE="ABQ_AM.ThermoMech.PatternBased.Activation"
**Slice Height, OriAX, OriAY, ORIAZ, OriBX, OriBY, OriBZ, OriCX, OriCY, OriCZ, Recoater time, Print start time, Total/StepTime
	{slice_height},		 1.,	 0.,	 0.,    0.,    1.,    0.,    0.,    0.,    0.,    		 8.83, 	   0.,			  "StepTime",
**-------------------
*PARAMETER TABLE,  TYPE="ABQ_AM.ThermoMech.PatternBased.Advanced"
**LayerByLayer/Sweep, Number of slices per time increment 
	  "LAYERBYLAYER", 		1,
**-------------------
*PARAMETER TABLE,  TYPE="ABQ_AM.ThermoMech.PatternBased.ScanStrategies"
** Scan strategy name
"Scan Strategy 1",
**-------------------
*PARAMETER TABLE,  TYPE="ABQ_AM.ThermoMech.PatternBased.ScanStrategy.Define", LABEL="Scan Strategy 1"
** Pattern name, Rot. angle,   Xmin,   Ymin,   Zmin,  Xmax,  Ymax,  Zmax
     "Pattern1", 		{rot_angle}, -1000., -1000., -1000., 1000., 1000., 1000.,
**-------------------
*PARAMETER TABLE,  TYPE="ABQ_AM.ThermoMech.PatternBased.Define", LABEL="Pattern1"
** xmin, ymin, xmax, ymax, label scan param, local in plane rotation
     0,   0,   {width_x},   {width_y},       "Power248",         0., 
**-------------------
*PARAMETER TABLE,  TYPE="ABQ_AM.ScanParameter.Define", LABEL="Power248"
**Power, Hatch Spacing, Speed, On Time Fraction
{power}, {hatch_spacing}, {scan_speed}, {on_time_fraction}
**-----------------------------------------------------
*TABLE COLLECTION, NAME="ABQ_TMP.ThermalPatternFlux"
**-------------------
*PARAMETER TABLE,  TYPE="ABQ_AM.ThermoMech.PatternParameters"
**Activation table collection
"ABQ_TMP.ThermalPatternActivation",
**-------------------
*PROPERTY TABLE,  TYPE="ABQ_AM.AbsorptionCoeff", DEPENDENCIES=0
** Absorptivity
0.45""".format(rot_angle = rotation_angle, power = laser_power,
                hatch_spacing = hatch_spacing, scan_speed = scan_speed,
                on_time_fraction = on_time_fraction, slice_height = slice_height,
               width_x = width_x, width_y = width_y),

"""*ELEMENT PROGRESSIVE ACTIVATION, NAME=__AM-Model-1_Deposition_EPA__, ELSET=AMPart-1.AMPartGeometry, FOLLOW=No""",

"""** STEP: LPBF_thermal
** 
*Step, name=LPBF_thermal, nlgeom=NO, inc=10000
*Heat Transfer, end=PERIOD, deltmx=10000.
{init_increment}, {total_time}, {min_increment}, {max_increment}, 
*ACTIVATE ELEMENTS , ACTIVATION = __AM-Model-1_Deposition_EPA__
"ABQ_TMP.ThermalPatternActivation"
*DFLUX
AMPart-1.AMPartGeometry , MBFNU , 1 , "ABQ_TMP.ThermalPatternFlux"
*FILM
AMPart-1.AMPartGeometry , FFS , 40 , 0.005
*RADIATE
AMPart-1.AMPartGeometry , RFS , 45 , 0.25
**""".format(init_increment = initial_increment, total_time = total_time,
                                                     min_increment = minimum_increment, max_increment = maximum_increment)
]


replacement_lines = [(new_lines + "\n").splitlines(True) for new_lines in new_content]

lines = replace_between_markers(lines, start_marker1, end_marker1, start_marker2, end_marker2, insert_marker, replacement_lines)

with open(inp_path, "w") as inp_file:
    inp_file.writelines(lines)

if not os.path.isfile(inp_path):
    raise RuntimeError(
        "Expected INP file was not created: {}".format(inp_path)
    )

print(
    "Created INP file for {}: {}".format(
        sample_name,
        inp_path,
    )
)