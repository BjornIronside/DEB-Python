import animal
import models
from visualizer import Plotter

if __name__ == '__main__':
    shark = animal.Animal(**animal.animals['shark'])
    model = models.STD(shark)

    model.solve(food_function=lambda t: 1, t_span=(0, 20000), step_size='auto', initial_state='birth')

    # print(model.sol)

    viz = Plotter(model)
    # viz.plot_state_vars()
    # viz.plot_powers()
    viz.plot_mineral_fluxes()

