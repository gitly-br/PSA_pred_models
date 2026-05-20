import { createStore, combineReducers, applyMiddleware, compose } from 'redux';
import keplerGlReducer, { enhanceReduxMiddleware } from '@kepler.gl/reducers';

const customizedKeplerGlReducer = keplerGlReducer.initialState({
  uiState: {
    readOnly: true,
    currentModal: null,
    activeSidePanel: null,
    mapControls: {
      visibleLayers: { show: false },
      toggle3d: { show: false },
      splitMap: { show: false },
      mapLegend: { show: true, active: true },
      mapDraw: { show: false },
      mapLocale: { show: false },
    },
  },
});

const reducers = combineReducers({
  keplerGl: customizedKeplerGlReducer,
});

const middlewares = enhanceReduxMiddleware([]);
const enhancers = applyMiddleware(...middlewares);

const store = createStore(reducers, {}, compose(enhancers));

export default store;
