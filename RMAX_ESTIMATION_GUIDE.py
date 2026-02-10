"""
Rmax Estimation in SPR Experiments - AffiLabs.core Implementation
=================================================================

Rmax (maximum response) is a critical parameter in SPR that represents the 
theoretical maximum binding capacity when all binding sites are saturated.

Your system uses THREE different approaches depending on the analysis type:

================================================================================
METHOD 1: Simple Kinetic Fitting (analysis_tab.py)
================================================================================

Location: affilabs/tabs/analysis_tab.py, line 916-943

Used for: Single-cycle 1:1 Langmuir binding analysis

Algorithm:
    1. Initial Guess: Rmax = max(observed_response) × 1.2
       - Takes peak response from experimental data
       - Adds 20% buffer to allow fitting above observed maximum
    
    2. Non-linear Least Squares Fitting:
       - Fits full Langmuir equation to association phase data:
       
         R(t) = Req × (1 - exp(-kobs × t)) + R0
         
         where:
         Req = Rmax × (ka × C) / (ka × C + kd)
         kobs = ka × C + kd
    
    3. Optimizes parameters: ka, kd, Rmax, R0 simultaneously
    
    4. Returns: Rmax ± standard error from fit

Advantages:
    - Simple, fast
    - Works for single concentration
    - Provides error estimates via lmfit

Limitations:
    - Less accurate than multi-concentration methods
    - Sensitive to baseline drift
    - Assumes perfect 1:1 binding


================================================================================
METHOD 2: Multi-Concentration Equilibrium Fitting (ka_kd_wizard.py)
================================================================================

Location: affilabs/widgets/ka_kd_wizard.py, line 169-175
         affilabs/utils/statistics.py, line 232-260

Used for: Global kinetic analysis across concentration series

This is the GOLD STANDARD method for accurate Rmax determination.

Algorithm (Multi-Step):

STEP 1: Local Rmax Estimation (per concentration)
    For each concentration i:
    
    a) Fit association phase to get local ka_i, kd_i:
       R(t) = (ka × C × Rmax) / (ka×C + kd) × [1 - exp(-(ka×C + kd)×t)]
    
    b) Calculate initial Rmax_i from:
       Rmax_i = b / (C_i × ka_i)
       where b = intercept from dR/dt vs R linear fit
    
    c) Outlier rejection:
       - Remove negative Rmax values
       - Remove values > 2× standard deviation from mean
       - Replace with average of positive values

STEP 2: Global ka, kd Determination
    - Plot kobs vs [C] where kobs = ka×C + kd
    - Linear regression: slope = ka, intercept = kd
    - This gives global ka, kd across all concentrations

STEP 3: Global Rmax Optimization
    - Collect equilibrium response (Req) from each concentration
    - Fit steady-state binding equation:
    
      Req = Rmax × C / (C + KD)
      
      where KD = kd / ka
    
    - Minimize chi-squared to find optimal Rmax:
    
      χ² = Σ[(Req_obs - Req_fit)² / (n - 1)]

Mathematical Formula (optimize_rmax):
    
    func_rmax([C, KD], Rmax) = [C[i] × Rmax / (C[i] + KD) for all i]
    
    Minimizes: χ²(func_rmax, Req_observed)

Advantages:
    - Most accurate method
    - Uses data from multiple concentrations
    - Accounts for KD in calculation
    - Robust outlier handling

Limitations:
    - Requires concentration series (≥3 concentrations)
    - Assumes equilibrium reached
    - More computationally intensive


================================================================================
METHOD 3: Affinity Fitting (statistics.py)
================================================================================

Location: affilabs/utils/statistics.py, line 62-114

Used for: Steady-state affinity analysis (dose-response curves)

Algorithm:
    1. Initial guess:
       Rmax₀ = max(response values)
       KD₀ = median(concentration values)
    
    2. Fit steady-state binding isotherm:
       
       R = Rmax × C / (C + KD)
    
    3. Minimize chi-squared using SLSQP optimization
    
    4. Returns: Rmax, KD, χ², p-value, fitted curve

Advantages:
    - Works with equilibrium data only
    - No time-course required
    - Direct determination of Rmax and KD

Limitations:
    - Requires true equilibrium
    - No kinetic information (ka, kd)
    - Sensitive to non-specific binding


================================================================================
THEORETICAL Rmax CALCULATION
================================================================================

For validation, you can calculate theoretical Rmax:

Formula:
    Rmax_theoretical = (MW_analyte / MW_ligand) × R_ligand × Stoichiometry

Where:
    MW_analyte   = Molecular weight of analyte (protein in solution)
    MW_ligand    = Molecular weight of immobilized ligand
    R_ligand     = Surface density of immobilized ligand (RU)
    Stoichiometry = Binding sites (usually 1 for 1:1, 2 for bivalent)

Example:
    If you immobilized 1000 RU of antibody (150 kDa) and inject antigen (50 kDa):
    
    Rmax = (50 / 150) × 1000 × 1 = 333 RU
    
This theoretical value should match your fitted Rmax within ±20%


================================================================================
COMPARISON OF METHODS
================================================================================

Method                  | Best For              | Data Required        | Accuracy
------------------------|----------------------|----------------------|---------
Simple Kinetic Fit      | Single concentration | Time-course, 1 conc  | Low
Multi-Conc Global Fit   | Kinetic analysis     | Time-course, 3+ conc | High ⭐
Affinity Fit            | Equilibrium only     | Steady-state, 3+ conc| Medium


================================================================================
YOUR IMPLEMENTATION SPECIFICS
================================================================================

Unit Conversions in Your Code:
    - Wavelength shift → Response Units (RU):
      
      RU = Δλ × 355.0
      
      (from analysis_tab.py line 914)
    
    - Concentration units handled: nM, µM, mM, M
      Internally converted to Molarity (M) for calculations

Fitting Library:
    - lmfit (analysis_tab.py) - Levenberg-Marquardt with bounds
    - scipy.optimize.minimize (statistics.py) - SLSQP method
    - scipy.optimize.curve_fit (statistics.py) - Trust Region Reflective

Error Handling:
    - All methods include:
      * Input validation (length checks, non-zero checks)
      * Division-by-zero protection (min value = 1e-10)
      * Convergence warnings
      * Try-except blocks with logging


================================================================================
RECOMMENDATIONS FOR YOUR PROTEIN UTILITY
================================================================================

To integrate with protein_utils.py, you could add:

1. Theoretical Rmax Calculator:
   ```python
   def calculate_theoretical_rmax(
       mw_analyte_da,
       mw_ligand_da,
       r_ligand_ru,
       stoichiometry=1
   ):
       return (mw_analyte_da / mw_ligand_da) * r_ligand_ru * stoichiometry
   ```

2. Rmax Validation:
   ```python
   def validate_rmax(experimental_rmax, theoretical_rmax, tolerance=0.2):
       ratio = experimental_rmax / theoretical_rmax
       return 1 - tolerance < ratio < 1 + tolerance
   ```

3. Activity Calculation:
   ```python
   def calculate_surface_activity(experimental_rmax, theoretical_rmax):
       # Percentage of active binding sites
       return (experimental_rmax / theoretical_rmax) * 100
   ```


================================================================================
EXAMPLE WORKFLOW
================================================================================

Real AffiLabs.core Analysis:

1. USER: Runs concentration series [10, 50, 100, 500 nM]

2. SYSTEM (ka_kd_wizard.py):
   - Fits each association curve → local Rmax estimates
   - Removes outliers
   - Fits global ka, kd from linear plot
   - Optimizes global Rmax from equilibrium responses
   
3. OUTPUT:
   - ka = 1.2 × 10⁵ M⁻¹s⁻¹
   - kd = 2.3 × 10⁻⁴ s⁻¹
   - KD = 1.92 nM
   - Rmax = 856 ± 12 RU

4. VALIDATION:
   - Compare to theoretical: 850 RU (within 1% ✓)
   - Surface activity: 100.7% (excellent)


================================================================================
KEY INSIGHTS
================================================================================

1. Your system intelligently chooses method based on data available:
   - Single cycle → Simple fit (Method 1)
   - Multi-cycle → Global fit (Method 2)
   - Steady-state only → Affinity fit (Method 3)

2. The multi-concentration global fit is most accurate because:
   - Averages noise across multiple experiments
   - KD-aware fitting reduces parameter correlation
   - Outlier rejection improves robustness

3. All methods protect against numerical instabilities:
   - Minimum denominators (1e-10)
   - Bounds on parameters (ka, kd, Rmax ≥ 0)
   - Convergence checks

4. Error propagation is included:
   - Standard errors from fit covariance matrix
   - Chi-squared goodness of fit
   - R² for linear models


================================================================================
REFERENCES IN YOUR CODE
================================================================================

Core Files:
    1. affilabs/tabs/analysis_tab.py (lines 916-990)
       - Simple 1:1 Langmuir fitting
    
    2. affilabs/widgets/ka_kd_wizard.py (lines 115-180)
       - Multi-concentration global analysis
    
    3. affilabs/utils/statistics.py
       - optimize_rmax() (lines 232-260)
       - optimize_by_affinity() (lines 76-114)
       - optimize_assoc() (lines 190-205)

Helper Functions:
    - func_rmax() - Steady-state binding equation
    - func_assoc() - Association phase equation
    - func_affinity_fit() - Langmuir isotherm
    - chi_squared() - Goodness of fit metric

Constants:
    - WAVELENGTH_TO_RU = 355.0 (conversion factor)
    - DEFAULT_FTOL = 1e-12 (optimization tolerance)


================================================================================
NEXT STEPS FOR INTEGRATION
================================================================================

If you want to add Rmax calculations to protein_utils.py:

1. Add theoretical Rmax calculator using UniProt MW data
2. Add validation against experimental Rmax values
3. Add surface activity % calculation
4. Export theoretical Rmax to Excel for comparison

Would you like me to implement any of these additions?
"""

if __name__ == '__main__':
    print(__doc__)
