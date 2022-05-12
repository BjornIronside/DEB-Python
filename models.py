from scipy.integrate import solve_ivp
import numpy as np
from pet import Pet


class STD:
    """
    class STD:

        Standard DEB model.
        Takes as input a Pet class.
        Calculates all fluxes based on state variables: Reserve (E), Structure (V), Maturity (E_H) and Reproduction
        Buffer (E_R).
        Integrates all state variables over time according to an input function of scaled functional feeding response
        (f) over time.
    """

    MAX_STEP_SIZE = 48 / 24  # Maximum step size during integration of state equations

    def __init__(self, organism):
        """Takes as input a Pet class or a dictionary of parameters to create a Pet class."""

        # Create the Pet class from the dictionary of parameters
        if isinstance(organism, dict):
            organism = Pet(**organism)
        # Check that organism is a Pet class
        elif not isinstance(organism, Pet):
            raise Exception("Input must be of class Pet or a dictionary of parameters to create a Pet class.")

        # Check validity of parameters of Pet
        if not organism.check_validity():
            raise Exception("Parameter values of Pet are not valid.")
        self.organism = organism
        self.sol = None  # Output from integration of state equations
        self.food_function = None  # Function of scaled functional feeding response (f) over time

    def simulate(self, food_function, t_span, step_size='auto', initial_state='birth'):
        """
        Integrates state equations over time. The output from the solver is stored in self.sol.

        :param food_function: Function of scaled functional feeding response (f) over time. Must be of signature
            f = food_function(time).
        :param t_span: (t0, tf). Interval of integration. The solver starts at t=t0 and integrates until it reaches
            t=tf.
        :param step_size: Step size of integration. If step_size='auto', the solver will decide the step size. Else
            input a numerical value for fixed step size.
        :param initial_state: Values of state variables at time t0. Format is (E, V, E_H, E_R). If initial_state='birth'
            the state variables are initialized with the values for birth (E_0, V_0, 0, 0), where E_0 and V_0 are
            defined in the Pet class.
        """

        # Get initial state
        if initial_state == 'birth':
            initial_state = (self.organism.E_0, self.organism.V_0, 0, 0)
        elif len(initial_state) != 4:
            raise Exception(f"Invalid input {initial_state} for initial state. The initial state must be a list or "
                            f"tuple of length 4 with format (E, V, E_H, E_R).")

        # Store the food function
        self.food_function = food_function

        # Define the times at which the solver should store the computed solution.
        if step_size == 'auto':
            t_eval = None
        elif isinstance(step_size, int) or isinstance(step_size, float):
            t_eval = np.arange(*t_span, step_size)
        else:
            raise Exception(f"Invalid step size value: {step_size}. Please select 'auto' for automatic step size during"
                            f" integration or input a fixed step size.")

        # Integrate the state equations
        self.sol = solve_ivp(self.state_changes, t_span, initial_state, t_eval=t_eval, max_step=self.MAX_STEP_SIZE)

    def state_changes(self, t, state_vars):
        """
        Computes the derivatives of the state variables according to the standard DEB model equations. Function used in
        the integration solver.
        :param t: time
        :param state_vars: tuple of state variables (E, V, E_H, E_R)
        :return: derivatives of the state variables (dE, dV, dE_H, dE_R)
        """

        # Unpacking state variables (Reserve (E), Structure (E), Maturity (E_H), Reproduction Buffer (E_R))
        E, V, E_H, E_R = state_vars

        # Computing fluxes
        p_A = self.p_A(V, E_H, t)
        p_C = self.p_C(E, V)
        p_S = self.p_S(V)
        p_G = self.p_G(p_C, p_S)
        p_J = self.p_J(E_H)
        p_R = self.p_R(p_C, p_J)

        # Changes to state variables
        dE = p_A - p_C
        dV = p_G / self.organism.E_G
        # Maturity or Reproduction Buffer logic
        if E_H < self.organism.E_Hp:
            dE_H = p_R
            dE_R = 0
        else:
            dE_H = 0
            dE_R = self.organism.kap_R * p_R
        return dE, dV, dE_H, dE_R

    def p_A(self, V, E_H, t):
        """
        Computes the assimilation power p_A.

        :param V: Scalar or array of Structure values
        :param E_H: Scalar or array of Maturity values
        :param t: Scalar or array of Time values
        :return: Scalar or array of assimilation power p_A values
        """
        if type(E_H) == np.ndarray:
            # Preallocate p_A
            p_A = np.zeros_like(E_H)
            for i, (structure, maturity, time) in enumerate(zip(V, E_H, t)):
                if maturity < self.organism.E_Hb:  # Embryo life stage
                    p_A[i] = 0
                else:
                    p_A[i] = self.organism.P_Am * self.food_function(time) * (structure ** (2 / 3))
            return p_A
        else:
            if E_H < self.organism.E_Hb:  # Embryo life stage
                return 0
            else:
                return self.organism.P_Am * self.food_function(t) * (V ** (2 / 3))

    def p_C(self, E, V):
        """
        Computes the mobilization power p_C.

        :param E: Scalar or array of Reserve values
        :param V: Scalar or array of Structure values
        :return: Scalar or array of mobilization power p_C values
        """
        return E * (self.organism.E_G * self.organism.v * (V ** (-1 / 3)) + self.organism.P_M) / \
               (self.organism.kappa * E / V + self.organism.E_G)

    def p_S(self, V):
        """
        Computes the somatic maintenance power p_S.

        :param V: Scalar or array of Structure values
        :return: Scalar or array of somatic maintenance power p_S values
        """
        return self.organism.P_M * V

    def p_G(self, p_C, p_S):
        """
        Computes the growth power p_G.

        :param p_C: Scalar or array of mobilization power values
        :param p_S: Scalar or array of somatic maintenance power values
        :return: Scalar or array of growth power p_G values
        """
        return self.organism.kappa * p_C - p_S

    # Maturity Maintenance Flux
    def p_J(self, E_H):
        """
        Computes the maturity maintenance power p_J

        :param E_H: Scalar or array of Maturity values
        :return: Scalar or array of maturity maintenance power p_J values
        """
        if type(E_H) == np.ndarray:
            p_J = np.zeros_like(E_H)
            for i, maturity in enumerate(E_H):
                if maturity < self.organism.E_Hp:
                    p_J[i] = self.organism.k_J * maturity
                else:  # Adult life stage
                    p_J[i] = self.organism.k_J * self.organism.E_Hp
            return p_J
        else:
            if E_H < self.organism.E_Hp:
                return self.organism.k_J * E_H
            else:  # Adult life stage
                return self.organism.k_J * self.organism.E_Hp

    # Maturation/Reproduction Flux
    def p_R(self, p_C, p_J):
        """
        Computes the reproduction power p_R

        :param p_C: Scalar or array of mobilization power values
        :param p_J: Scalar or array of maturity maintenance power values
        :return: Scalar or array of reproduction power p_R values
        """
        return (1 - self.organism.kappa) * p_C - p_J

    def p_D(self, p_S, p_J, p_R, E_H):
        """
        Computes the dissipation power p_D

        :param p_S: Scalar or array of somatic maintenance power values
        :param p_J: Scalar or array of maturity maintenance power values
        :param p_R: Scalar or array of reproduction power values
        :param E_H: Scalar or array of Maturity values
        :return: Scalar or array of dissipation power p_D values
        """
        if type(E_H) == np.ndarray:
            p_D = np.zeros_like(E_H)
            for i, (somatic_power, maturity_power, reproduction_power, maturity) in enumerate(zip(p_S, p_J, p_R, E_H)):
                if maturity < self.organism.E_Hp:
                    p_D[i] = somatic_power + maturity_power + reproduction_power
                else:
                    p_D[i] = somatic_power + maturity_power + (1 - self.organism.kap_R) * reproduction_power
            return p_D
        else:
            if E_H < self.organism.E_Hp:
                return p_S + p_J + p_R
            else:
                return p_S + p_J + (1 - self.organism.kap_R) * p_R

    def mineral_fluxes(self, p_A, p_D, p_G):
        """
        Computes the mineral fluxes from the assimilation power p_A, dissipation power p_D and growth power p_G.

        :param p_A: Scalar or array of assimilation power values
        :param p_D: Scalar or array of dissipation power values
        :param p_G: Scalar or array of growth power values
        :return: array of mineral fluxes values. Each row corresponds to the flux of CO2, H2O, O2 and N-Waste
            respectively.
        """
        if type(p_A) != np.ndarray:
            p_A = np.array([p_A])
            p_D = np.array([p_D])
            p_G = np.array([p_G])
        powers = np.array([p_A, p_D, p_G])
        return self.organism.eta_M @ powers


class STX(STD):
    # TODO: Check validity of Pet function (take code from __init__)
    """
    class STX:

        DEB model STX for mammals.
        Considers fetal development that starts after a preparation time t0. Until maturity E_Hx, the animal feeds on
        milk, which can have a higher nutritional value modelled by the parameter f_milk. Afterwards the animal switches
        to solid food.
        Takes as input a Pet class that must have parameters t_0 and E_Hx.
        Calculates all fluxes based on state variables: Reserve (E), Structure (V), Maturity (E_H) and Reproduction
        Buffer (E_R).
        Integrates all state variables over time according to an input function of scaled functional feeding response
        (f) over time.

    """

    def __init__(self, organism):
        """Takes as input a Pet class or a dictionary of parameters to create a Pet class."""

        # Create the Pet class from the dictionary of parameters
        if isinstance(organism, dict):
            organism = Pet(**organism)
        # Check that organism is a Pet class
        elif not isinstance(organism, Pet):
            raise Exception("Input must be of class Pet or a dictionary of parameters to create a Pet class.")

        # Check validity of parameters of Pet
        if not organism.check_validity():
            raise Exception("Parameter values of Pet are not valid.")

        # Check that the Pet class has parameters t_0 and E_Hx defined
        if not hasattr(organism, 't_0') or not hasattr(organism, 'E_Hx'):
            raise Exception('The organism is not compatible with model STX: parameters t_0 and E_Hx are required.')
        elif organism.t_0 <= 0:
            raise Exception("The time until gestation can't be negative.")  # TODO: Write the parameter name properly
        elif organism.E_Hx <= organism.E_Hb or organism.E_Hx >= organism.E_Hp:
            raise Exception("The weaning maturity level must be larger than the maturity at birth and smaller than "
                            "maturity at puberty.")
        # Set f_milk to 1 if it is not defined
        if not hasattr(organism, 'f_milk'):
            setattr(organism, 'f_milk', 1)
        elif organism.f_milk <= 0:
            raise Exception("The parameter f_milk must be positive")  # TODO: Write the exception text properly
        # Set the energy density of the mother to the maximum energy density
        if not hasattr(organism, 'E_density_mother'):
            setattr(organism, 'E_density_mother', organism.E_m)
        # Set initial reserve E_0
        setattr(organism, 'E_0', organism.E_density_mother * organism.V_0)

        super().__init__(organism)

    def state_changes(self, t, state_vars):
        """
        Computes the derivatives of the state variables according to the standard DEB model equations. Function used in
        the integration solver.
        :param t: time
        :param state_vars: tuple of state variables (E, V, E_H, E_R)
        :return: derivatives of the state variables (dE, dV, dE_H, dE_R)
        """

        # Unpacking state variables (Reserve (E), Structure (E), Maturity (E_H), Reproduction Buffer (E_R))
        E, V, E_H, E_R = state_vars

        # Computing fluxes
        p_A = self.p_A(V, E_H, t)
        p_C = self.p_C(E, V)
        p_S = self.p_S(V)
        p_G = self.p_G(p_C, p_S, V, E_H)
        p_J = self.p_J(E_H)
        p_R = self.p_R(p_C, p_J, p_S, p_G, E_H)

        # Pet is a foetus
        if E_H < self.organism.E_Hb:
            if t < self.organism.t_0:  # Gestation doesn't start until t=t_0
                dE, dV, dE_H, dE_R = 0, 0, 0, 0
            else:
                dE = self.organism.v * self.organism.E_density_mother * (V ** (2 / 3))
                dV = p_G / self.organism.E_G
                dE_H = p_R
                dE_R = 0
        else:
            dE = p_A - p_C
            dV = p_G / self.organism.E_G
            # Maturity or Reproduction Buffer logic
            if E_H < self.organism.E_Hp:
                dE_H = p_R
                dE_R = 0
            else:
                dE_H = 0
                dE_R = self.organism.kap_R * p_R

        return dE, dV, dE_H, dE_R

    def p_A(self, V, E_H, t):
        """
        Computes the assimilation power p_A.

        :param V: Scalar or array of Strucure values
        :param E_H: Scalar or array of Maturity values
        :param t: Scalar or array of Time values
        :return: Scalar or array of assimilation power p_A values
        """
        if type(E_H) == np.ndarray:
            p_A = np.zeros_like(E_H)
            for i, (structure, maturity, time) in enumerate(zip(V, E_H, t)):
                if maturity < self.organism.E_Hb:  # Pet is a foetus
                    p_A[i] = 0
                elif maturity < self.organism.E_Hx:  # Baby stage
                    p_A[i] = self.organism.P_Am * self.organism.f_milk * (structure ** (2 / 3))
                else:  # Adult
                    p_A[i] = self.organism.P_Am * self.food_function(time) * (structure ** (2 / 3))
            return p_A
        else:
            if E_H < self.organism.E_Hb:  # Pet is a foetus
                return 0
            elif E_H < self.organism.E_Hx:  # Baby stage
                return self.organism.P_Am * self.organism.f_milk * (V ** (2 / 3))
            else:  # Adult
                return self.organism.P_Am * self.food_function(t) * (V ** (2 / 3))

    def p_G(self, p_C, p_S, V, E_H):
        """
        Computes the growth power p_G.

        :param p_C: Scalar or array of mobilization power values
        :param p_S: Scalar or array of somatic maintenance power values
        :param V: Scalar or array of Structure values
        :param E_H: Scalar or array of Maturity values
        :return: Scalar or array of growth power p_G values
        """
        if type(E_H) == np.ndarray:
            p_G = np.zeros_like(E_H)
            for i, (maturity, mobil, soma_maint, structure) in enumerate(zip(E_H, p_C, p_S, V)):
                if maturity < self.organism.E_Hb:  # Pet is a foetus
                    p_G[i] = self.organism.E_G * self.organism.v * (structure ** (2 / 3))
                else:
                    p_G[i] = self.organism.kappa * mobil - soma_maint
            return p_G
        else:
            if E_H < self.organism.E_Hb:  # Pet is a foetus
                return self.organism.E_G * self.organism.v * (V ** (2 / 3))
            else:
                return self.organism.kappa * p_C - p_S

    def p_R(self, p_C, p_J, p_S, p_G, E_H):
        """
        Computes the reproduction power p_R

        :param p_C: Scalar or array of mobilization power values
        :param p_J: Scalar or array of maturity maintenance power values
        :param p_S: Scalar or array of somatic maintenance values
        :param p_G: Scalar or array of growth power values
        :param E_H: Scalar or array of Maturity values
        :return: Scalar or array of reproduction power p_R values
        """
        if type(E_H) == np.ndarray:
            p_R = np.zeros_like(E_H)
            for i, (maturity, mobil, mat_maint, soma_maint, growth) in enumerate(zip(E_H, p_C, p_J, p_S, p_G)):
                if maturity < self.organism.E_Hb:  # Pet is a foetus
                    p_R[i] = (1 - self.organism.kappa) * (soma_maint + growth) / self.organism.kappa - mat_maint
                else:
                    p_R[i] = (1 - self.organism.kappa) * mobil - mat_maint
            return p_R
        else:
            if E_H < self.organism.E_Hb:  # Pet is a foetus
                return (1 - self.organism.kappa) * (p_S + p_G) / self.organism.kappa - p_J
            else:
                return (1 - self.organism.kappa) * p_C - p_J


class Solution:
    # TODO: Have Solution class update whilst simulation is running
    # TODO: Keep track of maximum values of quantities of interest
    """
    Solution class:

    Stores the complete solution to the integration of state equations, including state variables, powers and fluxes, as
    well as time of stage transitions.
    """

    def __init__(self, model):

        self.model_type = type(model).__name__

        self.organism = model.organism

        self.t = model.sol.t
        self.E = model.sol.y[0]
        self.V = model.sol.y[1]
        self.E_H = model.sol.y[2]
        self.E_R = model.sol.y[3]

        self.calculate_powers(model)

        self.mineral_fluxes = model.mineral_fluxes(self.p_A, self.p_D, self.p_G)

        self.time_of_birth = None
        self.time_of_weaning = None
        self.time_of_puberty = None
        self.calculate_stage_transitions()

    def calculate_stage_transitions(self):
        """Calculates the time step of life stage transitions."""
        for t, E_H in zip(self.t, self.E_H):
            if not self.time_of_birth and E_H > self.organism.E_Hb:
                self.time_of_birth = t
            elif not self.time_of_weaning and hasattr(self.organism, 'E_Hx'):
                if E_H > self.organism.E_Hx:
                    self.time_of_weaning = t
            elif not self.time_of_puberty and E_H > self.organism.E_Hp:
                self.time_of_puberty = t

    def calculate_powers(self, model):
        """Computes all powers over every time step."""
        if self.model_type == 'STD':
            self.p_A = model.p_A(self.V, self.E_H, self.t)
            self.p_C = model.p_C(self.E, self.V)
            self.p_S = model.p_S(self.V)
            self.p_G = model.p_G(self.p_C, self.p_S)
            self.p_J = model.p_J(self.E_H)
            self.p_R = model.p_R(self.p_C, self.p_J)
            self.p_D = model.p_D(self.p_S, self.p_J, self.p_R, self.E_H)
        elif self.model_type == 'STX':
            self.p_A = model.p_A(self.V, self.E_H, self.t)
            self.p_C = model.p_C(self.E, self.V)
            self.p_S = model.p_S(self.V)
            self.p_G = model.p_G(self.p_C, self.p_S, self.V, self.E_H)
            self.p_J = model.p_J(self.E_H)
            self.p_R = model.p_R(self.p_C, self.p_J, self.p_S, self.p_G, self.E_H)
            self.p_D = model.p_D(self.p_S, self.p_J, self.p_R, self.E_H)
