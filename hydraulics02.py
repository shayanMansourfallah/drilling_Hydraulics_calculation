
from hydraulics01 import *

# print(drillstring.component_intervals)
# for i in range(0,len(a)-1):
#     mid = (a[i]+a[i+1])/2
#     print(drillstring.get_component_at_depth(mid).id,well.get_section_at_depth(mid).inner_diameter,sep="\t")


drill_pipe = DrillStringComponent(
    name="5.0-in Drill Pipe (Group 1)", 
    length=7000,    # 9,000 feet of standard drill pipe
    od=5.0, 
    id=4.276
)

hwdp = DrillStringComponent(
    name="5.0-in Heavy Weight Drill Pipe", 
    length=600.0,     # 600 feet of transitional heavy pipe
    od=5.0, 
    id=3.000
)

drill_collars = DrillStringComponent(
    name="6.5-in Drill Collars", 
    length=400.0,     # 400 feet of heavy collars to put weight on the bit
    od=6.5, 
    id=2.813
)

sec1 = WellboreSection(
    md_start=0.0, md_end=4000.0, 
    tvd_start=0.0, tvd_end=4000.0, 
    section_type='cased', inner_diameter=12.415
)
sec2 = WellboreSection(
    md_start=4000.0, md_end=8000.0, 
    tvd_start=4000.0, tvd_end=7850.0, # Handled deviation drop
    section_type='open_hole', inner_diameter=8.500
)
well = Wellbore([sec2, sec1]) # Swapped input order to test automatic sorting

bit_tfa_value = 0.460
drillstring = DrillString([drill_pipe,hwdp,drill_collars],bit_tfa=bit_tfa_value)
fluid = Fluid(10,drillstring,well)        
ve = AverageVelocity(100,well,drillstring)


bp = BinghamPlasticModel(3,6,30,50,ve,fluid,drillstring,well)
pl = PowerLawModel(3,6,30,50,ve,fluid,drillstring,well)
psi = PressureLoss(bp,ve,drillstring)


ccs = ContinuousAnalysisService(well,drillstring,100)
print(ccs._a)
print(ccs.section_midpoints)
print(well.get_section_at_depth(5000))
print(drillstring.get_component_at_depth(5000))
print(ve.annulus_velocity_calculator())
ccs.annulus_velocity_calculator(update_table=True)
print(ccs.sections)
