from dataclasses import dataclass
from typing import List, Optional , Tuple
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

@dataclass
class DrillStringComponent:
    """Represents a segment of the drill string (Drill Pipe, HWDP, Drill Collar)."""
    name: str
    length: float       # Linear length of this specific component segment (ft)
    od: float           # Outside Diameter (d_bo / d_po) in inches -> For Annulus calculations
    id: float           # Inside Diameter (d_bi / d_pi) in inches -> For Pipe calculations
    tool_joint_diamter : Optional[float] = None
    elasticity : Optional[float] = None
    possion_ration : Optional[float] = None
    ppf : Optional[float] = None
    
    
    def __post_init__(self):
        if self.length <= 0:
            raise ValueError(f"Length for {self.name} must be greater than 0.")
        if self.od <= self.id:
            raise ValueError(f"OD must be greater than ID for component: {self.name}")
        self
    
    def calculate_velocity(self,flow_rate):
        return 24.5 * flow_rate / (self.id**2 - self.od ** 2)

    def __repr__(self):
        return f"name: {self.name}\nod: {self.od}\nid: {self.id}\nlenght: {self.length}"
    
    
    

        
class DrillString:
    """Manages the assembly of drill string components and bit configuration."""
    
    def __init__(self, components: List[DrillStringComponent], bit_tfa: float = 0.0):
        """
        Initialize drill string components ordered from TOP (surface) to BOTTOM (bit).
        bit_tfa: Total Flow Area of the bit nozzles in square inches (needed for bit pressure drops).
        """
        self.components = components
        self.bit_tfa = bit_tfa
        self.component_intervals = self._calculate_intervals()

    def _calculate_intervals(self) -> pd.DataFrame:
        """Computes the top and bottom Measured Depths (MD) for each component based on length."""
        intervals = pd.DataFrame({},columns=['component','md_start','md_end','id','od','length'])
        current_md = 0.0
        
        for comp in self.components:
            md_start = current_md
            md_end = current_md + comp.length
            
            intervals.loc[len(intervals)] = [comp.name,md_start,md_end,comp.id,comp.od,comp.length]
            
            current_md = md_end
        return intervals
    
    
    
    def get_summary(self):
        for component in self.components:
            print(50*"="+"\n"
                  + component.name + ":\n"
                  + f"{component.name} outer diameter is: {component.od} inches\n"
                  + f"{component.name} inner diameter is: {component.id} inches\n"
                  + f"{component.name} length is: {component.length} feets")

    @property
    def total_length(self) -> float:
        """Returns the cumulative length of the drill string (Bit depth)."""
        # FIX: Changed 'if not self.component_intervals:' to '.empty'
        if self.component_intervals.empty:
            return 0.0
        return self.component_intervals.iloc[-1]['md_end']

    def get_component_at_depth(self, md: float) -> DrillStringComponent:
        """Finds which pipe component exists at a specific Measured Depth (MD)."""
        # If looking precisely at or slightly past bit depth due to small float variances
        if md >= self.total_length:
            return self.component_intervals[-1]['component']
            
        for _,interval in self.component_intervals.iterrows():
            if interval['md_start']<= md < interval['md_end']:
                return self.component_intervals.loc[_]
                
        raise ValueError(f"Depth {md} ft exceeds the length of the drill string ({self.total_length} ft).")
    

@dataclass
class WellboreSection:
    """Represents a physical section of the wellbore from the surface down."""
    md_start: float      # Measured Depth start (ft) -> Crucial for friction length
    md_end: float        # Measured Depth end (ft)
    tvd_start: float     # True Vertical Depth start (ft) -> Crucial for hydrostatic/ECD
    tvd_end: float       # True Vertical Depth end (ft)
    section_type: str    # 'cased' or 'open_hole'
    
    # Inner diameter of casing or hole size (d_h)
    inner_diameter: float 
    
    # Optional parameters for completeness
    casing_od: Optional[float] = None  

    

    def __post_init__(self):
        if self.md_end <= self.md_start:
            raise ValueError(f"md_end ({self.md_end}) must be greater than md_start ({self.md_start})")
        if self.inner_diameter <= 0:
            raise ValueError("Inner diameter must be greater than 0.")
        self.length = self.md_end-self.md_start


class Wellbore:
    """Manages the wellbore geometry profile and validates structure continuity."""
    
    def __init__(self, sections: List[WellboreSection]):
        # Automatically ensure sections are ordered from top to bottom
        self.sections = sorted(sections, key=lambda s: s.md_start)
        self._validate_sections()
        self.intervals = self.calculate_intervals()
        
    
    def _validate_sections(self):
        """Ensures the wellbore sections form a continuous path from surface (0)."""
        if not self.sections:
            raise ValueError("Wellbore must contain at least one section.")
            
        if self.sections[0].md_start != 0.0:
            raise ValueError("The first wellbore section must start at surface (MD = 0).")
            
        for i in range(len(self.sections) - 1):
            current_sec = self.sections[i]
            next_sec = self.sections[i + 1]
            
            # Gap or overlap check
            if current_sec.md_end != next_sec.md_start:
                raise ValueError(
                    f"Discontinuity detected between Section {i+1} and {i+2}. "
                    f"Expected MD start: {current_sec.md_end}, Got: {next_sec.md_start}"
                )
            
            
    def calculate_intervals(self):
        intervals = pd.DataFrame({},columns=['md_start','md_end','id','od','lenght'])
        for sec in self.sections:
            intervals.loc[len(intervals)] = [sec.md_start,sec.md_end,sec.inner_diameter,sec.casing_od,sec.length]
        return intervals
    def get_section_at_depth(self, md: float) -> WellboreSection:
        """Finds the wellbore section containing a given Measured Depth (MD)."""
        for section in self.sections:
            if section.md_start <= md <= section.md_end:
                return section
        raise ValueError(f"Depth {md} ft is out of bounds for the current wellbore profile.")
    
    def get_wellbore_id(self, md: float) -> float:
        """
        Returns the standalone wellbore inner boundary diameter (d_h) at a given depth.
        This is either the casing ID or the open hole diameter.
        """
        section = self.get_section_at_depth(md)
        return section.inner_diameter

    def get_section_lengths(self, section: WellboreSection) -> Tuple[float, float]:
        """Returns both the MD length (for friction) and TVD delta (for hydrostatics)."""
        md_length = section.md_end - section.md_start
        tvd_delta = section.tvd_end - section.tvd_start
        return md_length, tvd_delta
    
    def get_summary(self):
     for section in self.sections:
        print(50*"="+"\n"
              + f"The start measure depth is {section.md_start} feets and start TVD is {section.md_start} feets\n"
              + f"The end measure depth is {section.md_end} feets and start TVD is {section.md_end} feets\n"
              + f"The section type is: {section.section_type}\n"
              + f"The inner diameter is {section.inner_diameter} inches"
              )

    @property
    def total_measured_depth(self) -> float:
        """Returns the total measured depth (TMD) of the wellbore."""
        return self.sections[-1].md_end
    
    # Example usage for testing:

@dataclass
class AverageVelocity():
    flow_rate: float
    wellbore : Wellbore
    drill_string : DrillString
    
    def __post_init__(self):
        self.max_depth = self.drill_string.total_length
        self._a =  np.unique(np.concat((
            self.wellbore.intervals['md_start'],
            self.wellbore.intervals['md_end'],
            self.drill_string.component_intervals['md_start'],
            self.drill_string.component_intervals['md_end'])))
        
    def pipe_velocity_calculator(self):
        result = pd.DataFrame({},columns=['id','velocity_pipe'])
        for idx in range(0,len(self._a)-1):
                depth = (self._a[idx]+self._a[idx+1])/2
                dpi = self.drill_string.get_component_at_depth(depth)['id']
                average_velocity_pipe = 24.5 * self.flow_rate / dpi**2
                result.loc[len(result)] = [dpi,average_velocity_pipe]
        return result
    
    def annulus_velocity_calculator(self):
        result = pd.DataFrame({},columns=['dh','pipe_od','velocity_annulus'])
        for idx in range(0,len(self._a)-1):
                depth = (self._a[idx]+self._a[idx+1])/2
                dpo = self.drill_string.get_component_at_depth(depth)['od']
                dh = self.wellbore.get_wellbore_id(depth)
                average_velocity_annulus = 24.5* self.flow_rate / (dh**2 - dpo**2)
                result.loc[len(result)] = [dh,dpo,average_velocity_annulus]
        return result
                

@dataclass
class Fluid():
    density: float
    drillstring : DrillString
    well : Wellbore
    
    
    def __post_init__(self):
        pass

    def __str__(self):
        a = np.unique(np.concat((
            self.well.intervals['md_start'],
            self.well.intervals['md_end'],
            self.drillstring.component_intervals['md_start'],
            self.drillstring.component_intervals['md_end'])))
        a = np.unique(a)
        return(f"{a}")

@dataclass
class FannData():
    thetha3: float
    thetha6 : float
    thetha300 : float
    thetha600 : float

    def __post_init__(self):
        self.true_yield_stress = 2 * self.thetha3 - self.thetha6 #τy
        self.yield_point = 2 * self.thetha300 - self.thetha600
        self.R = self.true_yield_stress / self.yield_point

    def shear_rate_from_fann_speed(fann_speed:float)->float:
        return fann_speed * 1.703
    
@dataclass
class BinghamPlasticModel():
    theta3 : float
    theta6 : float
    theta300 : float
    theta600: float
    velocity_model : AverageVelocity
    fluid : Fluid
    drillstring : DrillString
    well : Wellbore

    def __post_init__(self):
        self.plastic_viscosity = self.theta600 -  self.theta300
        self.yield_point = self.theta300 - self.plastic_viscosity
        
        self._a =  np.unique(np.concat((
            self.well.intervals['md_start'],
            self.well.intervals['md_end'],
            self.drillstring.component_intervals['md_start'],
            self.drillstring.component_intervals['md_end'])))
        
    
    def pressure_loss_coefficient_annulus_calculator(self)->pd.DataFrame:
        Q = self.velocity_model.flow_rate
        mpaa = []
        Ra = []
        plc = []
        result = pd.DataFrame({},columns=['dh','do','mpaa','Ra','plc_annulus'])
        for idx in range(0,len(self._a)-1):
            depth = (self._a[idx] + self._a[idx+1])/2
            dh = self.well.get_wellbore_id(depth)
            dpo = self.drillstring.get_component_at_depth(depth)['od']
            
            mpaa_c = self.plastic_viscosity + 62.674773 * self.yield_point * (dh - dpo) * ((dh**2 - dpo**2) / Q)
            mpaa.append(mpaa_c)
            Ra_c = 1895.2796 * self.fluid.density * (dh - dpo) * (Q / (mpaa_c * (dh**2 - dpo**2)))

            if Ra_c > 2000 :
                pressure_loss_cofficient = (0.0012084581 * self.fluid.density **0.75 * self.plastic_viscosity**0.25 
                                            * self.velocity_model.flow_rate**1.75 ) / ((dh - dpo)**1.25 * (dh**2 - dpo**2)**1.75)
                plc.append(pressure_loss_cofficient)
            else :
                pressure_loss_cofficient = (0.053333333 * (self.yield_point / (dh - dpo)) + 
                         (0.0008488263 * self.plastic_viscosity * self.velocity_model.flow_rate) / 
                         ((dh - dpo)**2 * (dh**2 - dpo**2))) 
                plc.append(pressure_loss_cofficient)
            result.loc[len(result)] = [dh,dpo,mpaa_c,Ra_c,pressure_loss_cofficient]
    
        return result
    
    def pressure_loss_coefficient_pipe(self):

        Q = self.velocity_model.flow_rate
        result = pd.DataFrame({},columns=['id','mpap','Rp','plc_p'])
        mpap = []
        for idx in range(0,len(self._a)-1):
            depth = (self._a[idx] + self._a[idx+1])/2
            dpi = self.drillstring.get_component_at_depth(depth)['id']
            mpap_c = self.plastic_viscosity + 62.674773 * self.yield_point * (dpi**3 / Q)
            Rp = 1895.2796 * self.fluid.density * (Q / (mpap_c * dpi))
            if Rp > 2000:
                plc = (0.0012084581 * 
                       self.fluid.density**0.75 * self.plastic_viscosity**0.25 * self.velocity_model.flow_rate**1.75) / dpi**4.75
            else :
                plc = (0.053333333 * self.yield_point / dpi) + (0.0008488263 * self.plastic_viscosity * self.velocity_model.flow_rate / dpi**4)
            result.loc[len(result)] = [dpi,mpap_c,Rp,plc]
            
        
        return result
@dataclass 
class PressureLoss():

    bingham_model : BinghamPlasticModel
    velocity : AverageVelocity
    drill_string : DrillString

    def __post_init__(self):
        pass

    def tool_joint_pressure_loss(self):
        """
        Calculate tool joint pressure loss for each component.
        
        Returns:
            DataFrame with columns: ['name', 'id', 'Rp', 'mpap_c', 'ktj', 
                                    'loss_per_joint_psi', 'num_joints', 'total_loss_psi']
        """
        result = pd.DataFrame({}, columns=[
            'name', 'id', 'length_ft', 'Rp', 'mpap_c', 'ktj', 
            'velocity_fts', 'loss_per_joint_psi', 'num_joints', 'total_loss_psi'
        ])
        
        for comp in self.drill_string.components:
            # Skip if no tool joint diameter defined
            # if comp.tool_joint_diamter is None:
            #     continue
                
            # 1. Calculate apparent viscosity for pipe (mpap)
            mpap_c = (self.bingham_model.plastic_viscosity + 
                    62.674773 * self.bingham_model.yield_point * (comp.id**3 / self.velocity.flow_rate))
            
            # 2. Calculate Reynolds number in pipe (Page 3)
            Rp = 1895.2796 * self.bingham_model.fluid.density * (self.velocity.flow_rate / (mpap_c * comp.id))
            
            # 3. Calculate velocity in pipe (ft/s)
            velocity_fts = 24.5 * self.velocity.flow_rate / (60 * comp.id**2)
            
            # 4. Determine tool joint loss coefficient (ktj) based on Rp (Page 34-35)
            if Rp <= 1000:
                ktj = 0.0
            elif 1000 < Rp <= 3000:
                ktj = 1.91 * np.log10(Rp) - 5.64
            elif 3000 < Rp <= 13000:
                ktj = 4.66 - (1.05 * np.log10(Rp))
            else:  # Rp > 13000
                ktj = 0.33
            
            # 5. Calculate pressure loss per tool joint (psi)
            # Convert density from lb/gal to lb/ft³
            density_lbft3 = self.bingham_model.fluid.density * 7.48052
            
            # Δptj = (ρ × κtj × vf²) / 2, then convert to psi
            loss_per_joint_psi = (density_lbft3 * ktj * velocity_fts**2) / (2 * 144)
            
            # 6. Calculate number of tool joints in this component
            joint_length = 30.0  # ft (typical)
            num_joints = int(comp.length / joint_length)
            
            # 7. Total pressure loss for this component
            total_loss_psi = loss_per_joint_psi * num_joints
            
            # Store results
            result.loc[len(result)] = [
                comp.name,
                comp.id,
                comp.length,
                Rp,
                mpap_c,
                ktj,
                velocity_fts,
                loss_per_joint_psi,
                num_joints,
                total_loss_psi
            ]
        
        return result



@dataclass
class PowerLawModel():
    theta3: float
    theta6: float
    theta300: float
    theta600: float
    velocity_model: AverageVelocity
    fluid: Fluid
    drillstring: DrillString
    well: Wellbore

    def __post_init__(self):
        """Calculate Power Law parameters from Fann data (Page 14 & 22)."""
        # Flow Behavior Index (Page 22)
        # n = 3.321928091 * log(θ600/θ300)
        self.flow_behavior_index = 3.321928091 * np.log10(self.theta600 / self.theta300)
        
        # Consistency Factor (Page 22)
        # K = 510 * θ300 / (1.703 * 300)^n
        self.consistency_factor = (510 * self.theta300) / (1.703 * 300) ** self.flow_behavior_index
        
        # Get depth intervals (same as Bingham)
        self._a = np.unique(np.concat((
            self.well.intervals['md_start'],
            self.well.intervals['md_end'],
            self.drillstring.component_intervals['md_start'],
            self.drillstring.component_intervals['md_end'])))
    
    
    def pressure_loss_coefficient_annulus_calculator(self) -> pd.DataFrame:
        Q = self.velocity_model.flow_rate
        gc = 32.174
        
        # Convert density from lb/gal to lb/ft³
        rho = self.fluid.density * 7.48052  # lb/ft³
        
        result = pd.DataFrame({}, columns=['dh', 'do', 'n', 'K', 'Ga', 'Re_annulus', 'fa', 'plc_annulus'])
        
        for idx in range(0, len(self._a) - 1):
            depth = (self._a[idx] + self._a[idx + 1]) / 2
            dh = self.well.get_wellbore_id(depth)
            dpo = self.drillstring.get_component_at_depth(depth)['od']
            
            # Average velocity in annulus (ft/min)
            v_aa_ftmin = 24.5 * Q / (dh**2 - dpo**2)
            # Convert to ft/s
            v_aa = v_aa_ftmin / 60
            
            # Convert diameters from inches to ft
            dh_ft = dh / 12
            dpo_ft = dpo / 12
            
            n = self.flow_behavior_index
            K = self.consistency_factor
            Ga = ((2 * n + 1) / (2 * n)) ** n * 8 ** (n - 1)
            
            # Reynolds number (Page 24) - with proper units
            Re = (rho * v_aa ** (2 - n) * (dh_ft - dpo_ft) ** n) / (gc * (2/3) * Ga * K)
            
            # Friction factor
            fa = self._calculate_friction_factor_annulus(Re, n)
            
            # Pressure loss (Page 28) - dp/dl
            plc = (rho / gc) * v_aa**2 * fa * (2 / (dh_ft - dpo_ft))
            
            # Convert to consistent units (psi/ft)
            # 1 psi = 144 lbf/ft², so divide by 144
            plc_psi = plc / 144
            
            result.loc[len(result)] = [dh, dpo, n, K, Ga, Re, fa, plc_psi]
        
        return result

    def pressure_loss_coefficient_pipe(self) -> pd.DataFrame:
        """Calculate pipe pressure loss using Power Law model.
        
        This requires:
        1. Geometry factor for pipe (Page 24)
        2. Average velocity in pipe (Page 23)
        3. Reynolds number for pipe (Page 24)
        4. Friction factor for pipe (Page 25)
        5. Pressure loss (Page 27)
        """
        Q = self.velocity_model.flow_rate
        result = pd.DataFrame({}, columns=['id', 'n', 'K', 'Gp', 'Re_pipe', 'fp', 'plc_pipe'])
        
        for idx in range(0, len(self._a) - 1):
            depth = (self._a[idx] + self._a[idx + 1]) / 2
            dpi = self.drillstring.get_component_at_depth(depth)['id']
            
            # 1. Average velocity in pipe (Page 23)
            v_p = 24.5 * Q / dpi**2
            
            # 2. Geometry factor for pipe (Page 24)
            # Gp = [((3n+1)/(4n))^n] * 8^(n-1)
            n = self.flow_behavior_index
            Gp = ((3 * n + 1) / (4 * n)) ** n * 8 ** (n - 1)
            
            # 3. Reynolds number for pipe (Page 24)
            # Re = (ρ * v^(2-n) * dpi^n) / (gc * Gp * K)
            K = self.consistency_factor
            gc = 32.174
            Re = (self.fluid.density * v_p ** (2 - n) * dpi ** n) / (gc * Gp * K)
            
            # 4. Friction factor for pipe (Page 25)
            fp = self._calculate_friction_factor_pipe(Re, n)
            
            # 5. Pressure loss (Page 27)
            # Ploss = (ρ/gc) * v^2 * fp * Ls * (2/dpi)
            # For dp/dl (without Ls):
            plc = (self.fluid.density / gc) * v_p**2 * fp * (2 / dpi)
            
            result.loc[len(result)] = [dpi, n, K, Gp, Re, fp, plc]
        
        return result
    
    def _calculate_friction_factor_annulus(self, Re: float, n: float) -> float:
        """Calculate friction factor for annulus (Page 26).
        
        Three regimes:
        1. Laminar: fa = 24/Re
        2. Transition: interpolation
        3. Turbulent: fa = a/Re^b
        """
        R_l = 2100  # Laminar boundary
        R_t = 4000  # Turbulent boundary (if using transition)
        
        if Re <= R_l:
            # Laminar flow
            return 24 / Re
        elif R_l < Re < R_t:
            # Transition flow (Page 26)
            a = (np.log10(n) + 3.93) / 50
            b = (1.75 - np.log10(n)) / 7
            f_l = 24 / R_l
            f_t = a / R_l**b
            return f_l + ((Re - R_l) / 800) * (f_t - f_l)
        else:
            # Turbulent flow (Page 27)
            a = (np.log10(n) + 3.93) / 50
            b = (1.75 - np.log10(n)) / 7
            return a / Re**b
    
    def _calculate_friction_factor_pipe(self, Re: float, n: float) -> float:
        """Calculate friction factor for pipe (Page 25).
        
        Three regimes:
        1. Laminar: fp = 16/Re
        2. Transition: interpolation
        3. Turbulent: fp = a/Re^b
        """
        R_l = 2100  # Laminar boundary
        R_t = 4000  # Turbulent boundary
        
        if Re <= R_l:
            # Laminar flow
            return 16 / Re
        elif R_l < Re < R_t:
            # Transition flow (Page 25)
            a = (np.log10(n) + 3.93) / 50
            b = (1.75 - np.log10(n)) / 7
            f_l = 16 / R_l
            f_t = a / R_l**b
            return f_l + ((Re - R_l) / 800) * (f_t - f_l)
        else:
            # Turbulent flow (Page 26)
            a = (np.log10(n) + 3.93) / 50
            b = (1.75 - np.log10(n)) / 7
            return a / Re**b   

@dataclass
class Herschel_Bulkley_Model():
    fann_data : FannData
    
    def __post_init__(self):
        self.thetha600 = self.fann_data.thetha600
        self.thetha300 = self.fann_data.thetha300

        n_from_R = 3.32 * (np.log10(
            (self.thetha600 - self.fann_data.true_yield_stress) / 
            (self.thetha300 - self.fann_data.true_yield_stress)))
        
        self.flow_behaviour_index = n_from_R

        k_from_R = (self.thetha300 - self.fann_data.true_yield_stress) / (511.0 ** self.flow_behaviour_index) 

        self.consistency_factor = k_from_R
@dataclass
class ContinuousAnalysisService():
    wellbore:Wellbore
    drillstring : DrillString
    flow_rate : float
    bingham_model : BinghamPlasticModel
    herschel_bulkley_model : Herschel_Bulkley_Model
    def __post_init__(self):
        self._a =  np.unique(np.concat((
            self.wellbore.intervals['md_start'],
            self.wellbore.intervals['md_end'],
            self.drillstring.component_intervals['md_start'],
            self.drillstring.component_intervals['md_end'])))
        self.section_midpoints = (self._a[:-1]+self._a[1:]) / 2
        self.sections = self.geometry_sections_describer()
        self.sections_pipe_velocity = self.pipe_velocity_calculator()
        

    def geometry_sections_describer(self):
        geometry = pd.DataFrame({},columns=['pipe_name','md_start','md_end','hole_id','pipe_od','pipe_id'])
        depth = self.section_midpoints
        for i,md in enumerate(depth):
             
            well = self.wellbore.get_section_at_depth(md)
            drill_string = self.drillstring.get_component_at_depth(md)
            geometry.loc[len(geometry)] = [drill_string['component'],
                                           self._a[i],
                                           self._a[i+1],
                                           well.inner_diameter,
                                           drill_string['od'],
                                           drill_string['id']]
            
        return geometry
    

    
            
    def pipe_velocity_calculator(self,update_table:Optional[bool] = None):
        velocity = 24.5 * self.flow_rate / (self.geometry_sections_describer()['pipe_id'] **2 ).to_numpy().flatten()
        if update_table :
            self.sections['pipe_velocity'] = velocity
        return velocity
    
    def annulus_velocity_calculator(self,update_table:Optional[bool]):
        dh = self.sections['hole_id'] 
        dpo = self.sections['pipe_od'] 
        velocity = 24.5 * self.flow_rate / (dh **2 - dpo **2 ).to_numpy().flatten()
        if update_table :
            self.sections['annulur_velocity'] = velocity
        return velocity
    
    def pipe_pf_calculator(self):
        alpha = 0
        n = self.herschel_bulkley_model.flow_behaviour_index
        k = self.herschel_bulkley_model.consistency_factor

        self._B_a = (((3.0 - alpha) * n + 1.0) / ((4.0 - alpha) * n)) * (1.0 + alpha / 2.0)
        d_hyd = self.sections['pipe_id'].to_numpy().flatten()
        shear_rate_at_wall = 1.6 * self._B_a / self.sections_pipe_velocity 
    

        
    