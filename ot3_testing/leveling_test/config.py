from ot3_testing.leveling_test.type import SlotName, Mount, Point, TestNameLeveling, Direction

LevelingSetting = {

    TestNameLeveling.Z_Leveling: {
        Mount.RIGHT: {
            SlotName.A1: {
                Direction.Z: {
                    "point": Point(5, 410, 357),
                    "compensation": {"below_rear": -0.056, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}
            },
            SlotName.A2: {
                Direction.Z: {
                    "point": Point(175, 410, 357),
                    "compensation": {"below_rear": -0.07, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}

            },
            SlotName.A3: {
                Direction.Z: {
                    "point": Point(335, 410, 357),
                    "compensation": {"below_rear": -0.062, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}
            },

            SlotName.B1: {
                Direction.Z: {
                    "point": Point(5, 305, 357),
                    "compensation": {"below_rear": -0.17, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}
            },
            SlotName.B2: {
                Direction.Z: {
                    "point": Point(175, 305, 357),
                    "compensation": {"below_rear": -0.088, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}
            },
            SlotName.B3: {
                Direction.Z: {
                    "point": Point(335, 305, 357),
                    "compensation": {"below_rear": -0.068, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}
            },

            SlotName.C1: {
                Direction.Z: {
                    "point": Point(5, 197, 357),
                    "compensation": {"below_rear": -0.098, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}
            },
            SlotName.C2: {
                Direction.Z: {
                    "point": Point(175, 197, 357),
                    "compensation": {"below_rear": -0.03, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}
            },
            SlotName.C3: {
                Direction.Z: {
                    "point": Point(335, 197, 357),
                    "compensation": {"below_rear": -0.044, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}
            },

            SlotName.D1: {
                Direction.Z: {
                    "point": Point(5, 92, 357),
                    "compensation": {"below_rear": -0.05, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}
            },
            SlotName.D2: {
                Direction.Z: {
                    "point": Point(175, 92, 357),
                    "compensation": {"below_rear": -0.15, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}
            },
            SlotName.D3: {
                Direction.Z: {
                    "point": Point(335, 92, 357),
                    "compensation": {"below_rear": -0.058, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Y: {}
            },
        },
        Mount.LEFT: {
                    SlotName.C2: {
                        Direction.Z: {
                            "point": Point(215, 197, 357),
                            "compensation": {"below_rear": 0.014, "below_front": 0},
                            "channel_definition": {
                                "below_rear": 3,
                                "below_front": 2
                            }
                        },
                        Direction.X: {},
                        Direction.Y: {}
                    }
                }
    },

    TestNameLeveling.CH8_Leveling: {
        Mount.RIGHT: {
            SlotName.A2: {
                Direction.Y: {
                    "point": Point(335.94, 412.22, 299.16),
                    "compensation": {"right_rear": -0.056, "right_front": 0},
                    "channel_definition": {
                        "right_front": 0,
                        "right_rear": 1
                    }
                },
                Direction.X: {},
                Direction.Z: {}
            },
            SlotName.C1: {
                Direction.Y: {
                    "point": Point(172.07, 197.18, 299.16),
                    "compensation": {"right_rear": -0.07, "right_front": 0},
                    "channel_definition": {
                        "right_front": 0,
                        "right_rear": 1
                    }
                },
                Direction.X: {},
                Direction.Z: {}

            },
            SlotName.C3: {
                Direction.Y: {
                    "point": Point(499.83, 197.18, 299.16),
                    "compensation": {"right_rear": -0.062, "right_front": 0},
                    "channel_definition": {
                        "right_front": 0,
                        "right_rear": 1
                    }
                },
                Direction.X: {},
                Direction.Z: {}
            }
        },
        Mount.LEFT: {
            SlotName.C1: {
                Direction.Y: {
                    "point": Point(215.42, 198.33, 299.16),
                    "compensation": {"right_rear": 0.014, "right_front": 0},
                    "channel_definition": {
                        "right_front": 0,
                        "right_rear": 1
                    }
                },
                Direction.X: {},
                Direction.Z: {}
            }
        }
    },

    TestNameLeveling.CH96_Leveling: {
        Mount.LEFT: {
            SlotName.A2: {
                Direction.Y: {
                    "point": Point(387, 421, 318),
                    "compensation": {"right_rear": -0.086, "right_front": 0},
                    "channel_definition": {
                        "right_rear": 1,
                        "right_front": 0
                    }
                },
                Direction.X: {
                    "point": Point(213, 305, 300),
                    "compensation": {"front_left": 0, "front_right": 0.048},
                    "channel_definition": {
                        "front_left": 4,
                        "front_right": 5
                    }
                },
                Direction.Z: {
                    "point": Point(218, 424, 390.5),
                    "compensation": {"below_rear_left": -0.056, "below_rear_right": -0.09, "below_front_left": 0,
                                     "below_front_right": 0.078},
                    "channel_definition": {
                        "below_rear_left": 10,
                        "below_rear_right": 11,
                        "below_front_left": 8,
                        "below_front_right": 9
                    }
                },
            },

            SlotName.C1: {
                Direction.Y: {
                    "point": Point(223, 203, 318),
                    "compensation": {"right_rear": -0.006, "right_front": 0},
                    "channel_definition": {
                        "right_rear": 1,
                        "right_front": 0
                    }
                },
                Direction.X: {
                    "point": Point(50, 91, 300),
                    "compensation": {"front_left": 0, "front_right": 0.054},
                    "channel_definition": {
                        "front_left": 4,
                        "front_right": 5
                    }
                },
                Direction.Z: {}
            },

            SlotName.C3: {
                Direction.Y: {
                    "point": Point(207, 203, 318),
                    "compensation": {"left_rear": -0.054, "left_front": 0},
                    "channel_definition": {
                        "left_rear": 3,
                        "left_front": 2
                    }
                },
                Direction.X: {
                    "point": Point(382, 91, 300),
                    "compensation": {"front_left": 0, "front_right": 0.036},
                    "channel_definition": {
                        "front_left": 4,
                        "front_right": 5
                    }
                },
                Direction.Z: {}
            },

            SlotName.D1: {
                Direction.Y: {},
                Direction.X: {},
                Direction.Z: {
                    "point": Point(51, 99, 318),
                    "compensation": {"below_rear_left": -0.056, "below_rear_right": -0.078,
                                     "below_front_left": 0, "below_front_right": 0.082},
                    "channel_definition": {
                        "below_rear_left": 10,
                        "below_rear_right": 11,
                        "below_front_left": 8,
                        "below_front_right": 9
                    }
                },
            },

            SlotName.D3: {
                Direction.Y: {},
                Direction.X: {},
                Direction.Z: {
                    "point": Point(377, 99, 318),
                    "compensation": {"below_rear_left": -0.058, "below_rear_right": -0.092,
                                     "below_front_left": 0, "below_front_right": 0.05},
                    "channel_definition": {
                        "below_rear_left": 10,
                        "below_rear_right": 11,
                        "below_front_left": 8,
                        "below_front_right": 9
                    }
                },
            },

            SlotName.C2: {
                Direction.Y: {},
                Direction.X: {},
                Direction.Z: {
                    "point": Point(214, 210, 318),
                    "compensation": {"below_rear_left": -0.047, "below_rear_right": -0.052,
                                     "below_front_left": 0.0, "below_front_right": 0.022},
                    "channel_definition": {
                        "below_rear_left": 10,
                        "below_rear_right": 11,
                        "below_front_left": 8,
                        "below_front_right": 9
                    }
                },
            },

        },

        Mount.RIGHT: {

            }
    },

    TestNameLeveling.Gripper_Leveling: {
        Mount.LEFT: {
            SlotName.C2: {
                Direction.X: {
                    "point": Point(52, 332.5, 500),
                    "compensation": {"rear_left": -0.003, "rear_right": 0},
                    "channel_definition": {"rear_left": 1, "rear_right": 0}
                },
                Direction.Y: {
                    "point": Point(223.5, 181.7, 500),
                    "compensation": {"right_front": 0, "right_rear": -0.029},
                    "channel_definition": {"right_front": 2, "right_rear": 3}
                },
                Direction.Z: {
                    "point": Point(202.5, 177, 500),
                    "compensation": {"below_rear": 0.04, "below_front": 0},
                    "channel_definition": {"below_rear": 5, "below_front": 4}
                }
            }
        },
        Mount.RIGHT: {
        }
    }
}
