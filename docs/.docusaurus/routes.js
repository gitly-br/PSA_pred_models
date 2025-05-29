import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/PSA_pred_models/__docusaurus/debug',
    component: ComponentCreator('/PSA_pred_models/__docusaurus/debug', '5bd'),
    exact: true
  },
  {
    path: '/PSA_pred_models/__docusaurus/debug/config',
    component: ComponentCreator('/PSA_pred_models/__docusaurus/debug/config', '8d6'),
    exact: true
  },
  {
    path: '/PSA_pred_models/__docusaurus/debug/content',
    component: ComponentCreator('/PSA_pred_models/__docusaurus/debug/content', 'daf'),
    exact: true
  },
  {
    path: '/PSA_pred_models/__docusaurus/debug/globalData',
    component: ComponentCreator('/PSA_pred_models/__docusaurus/debug/globalData', 'bdd'),
    exact: true
  },
  {
    path: '/PSA_pred_models/__docusaurus/debug/metadata',
    component: ComponentCreator('/PSA_pred_models/__docusaurus/debug/metadata', '9fa'),
    exact: true
  },
  {
    path: '/PSA_pred_models/__docusaurus/debug/registry',
    component: ComponentCreator('/PSA_pred_models/__docusaurus/debug/registry', '3bf'),
    exact: true
  },
  {
    path: '/PSA_pred_models/__docusaurus/debug/routes',
    component: ComponentCreator('/PSA_pred_models/__docusaurus/debug/routes', 'b78'),
    exact: true
  },
  {
    path: '/PSA_pred_models/markdown-page',
    component: ComponentCreator('/PSA_pred_models/markdown-page', 'c92'),
    exact: true
  },
  {
    path: '/PSA_pred_models/',
    component: ComponentCreator('/PSA_pred_models/', '107'),
    routes: [
      {
        path: '/PSA_pred_models/',
        component: ComponentCreator('/PSA_pred_models/', '77e'),
        routes: [
          {
            path: '/PSA_pred_models/',
            component: ComponentCreator('/PSA_pred_models/', 'ec2'),
            routes: [
              {
                path: '/PSA_pred_models/',
                component: ComponentCreator('/PSA_pred_models/', '253'),
                exact: true,
                sidebar: "tutorialSidebar"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    path: '*',
    component: ComponentCreator('*'),
  },
];
