from ot3_testing.leveling_test.type import SlotName, Mount, Point, TestNameLeveling, Direction

LevelingSetting = {

    TestNameLeveling.Z_Leveling: {
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
        },
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
        }
    },

    TestNameLeveling.CH8_Leveling: {
        Mount.LEFT: {
            SlotName.C1: {
                Direction.Y: {
                    "point": Point(215, 197, 357),
                    "compensation": {"below_rear": 0.014, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Z: {}
            }
        },
        Mount.RIGHT: {
            SlotName.A2: {
                Direction.Y: {
                    "point": Point(5, 410, 357),
                    "compensation": {"below_rear": -0.056, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Z: {}
            },
            SlotName.C1: {
                Direction.Y: {
                    "point": Point(175, 410, 357),
                    "compensation": {"below_rear": -0.07, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {},
                Direction.Z: {}

            },
            SlotName.C3: {
                Direction.Y: {
                    "point": Point(335, 410, 357),
                    "compensation": {"below_rear": -0.062, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
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
                    "point": Point(215, 197, 357),
                    "compensation": {"below_rear": 0.014, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {
                    "point": Point(215, 197, 357),
                    "compensation": {"below_rear": 0.014, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.Z: {
                    "point": Point(215, 197, 357),
                    "compensation": {"below_rear": 0.014, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
            },

            SlotName.C1: {
                Direction.Y: {
                    "point": Point(215, 197, 357),
                    "compensation": {"below_rear": 0.014, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {
                    "point": Point(215, 197, 357),
                    "compensation": {"below_rear": 0.014, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.Z: {}
            },

            SlotName.C3: {
                Direction.Y: {
                    "point": Point(215, 197, 357),
                    "compensation": {"below_rear": 0.014, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.X: {
                    "point": Point(215, 197, 357),
                    "compensation": {"below_rear": 0.014, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                },
                Direction.Z: {}
            },

            SlotName.D1: {
                Direction.Y: {},
                Direction.X: {},
                Direction.Z: {
                    "point": Point(215, 197, 357),
                    "compensation": {"below_rear": 0.014, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                }
            },

            SlotName.D3: {
                Direction.Y: {},
                Direction.X: {},
                Direction.Z: {
                    "point": Point(215, 197, 357),
                    "compensation": {"below_rear": 0.014, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                }
            },

            SlotName.C2: {
                Direction.Y: {},
                Direction.X: {},
                Direction.Z: {
                    "point": Point(215, 197, 357),
                    "compensation": {"below_rear": 0.014, "below_front": 0},
                    "channel_definition": {
                        "below_rear": 3,
                        "below_front": 2
                    }
                }
            },
        },
        Mount.RIGHT: {

        }
    }
}
