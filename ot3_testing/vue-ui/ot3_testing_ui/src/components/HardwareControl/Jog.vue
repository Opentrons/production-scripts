<template>
    <div class="jog">

        <el-row :gutter="20">
            <el-col :span="8">
                <div>
                    <el-divider content-position="center">
                        <span>Jogging Parameter</span>
                    </el-divider>

                </div>
                <div class="jogging_parameter">
                    <div class="listenning_switch">
                     
                    </div>

                    <div class="slider-demo-block">
                        <span class="demonstration">Step-X</span>
                        <el-slider show-input />
                    </div>
                    <div class="slider-demo-block">
                        <span class="demonstration">Step-Y</span>
                        <el-slider show-input />
                    </div>
                    <div class="slider-demo-block">
                        <span class="demonstration">Step-Z</span>
                        <el-slider show-input />
                    </div>
                    <div class="slider-demo-block">
                        <span class="demonstration">Step-ZG</span>
                        <el-slider show-input />
                    </div>
                    <div class="slider-demo-block">
                        <span class="demonstration">Step-G</span>
                        <el-slider show-input />
                    </div>
                </div>

            </el-col>
            <el-col :span="8">
                <div>
                    <el-divider content-position="center">
                        <span>Pipette Control</span>
                    </el-divider>

                </div>
                <div class="pipette_control">
                    <el-row :gutter="20">
                        <el-col :span="6" :offset="6">
                            <span class="Arrow">
                                <el-icon :size="50">
                                    <ArrowUpBold />
                                </el-icon>
                            </span>
                        </el-col>
                        <el-col :span="6" :offset="6">
                            <span class="Arrow">
                                <el-icon :size="50">
                                    <ArrowUpBold />
                                </el-icon>
                            </span>
                        </el-col>
                    </el-row>
                    <el-row :gutter="20">
                        <el-col :span="6">
                            <span class="Arrow">
                                <el-icon :size="50">
                                    <ArrowLeftBold />
                                </el-icon>
                            </span>
                        </el-col>
                        <el-col :span="6" :offset="6">
                            <span class="Arrow">
                                <el-icon :size="50">
                                    <ArrowRightBold />
                                </el-icon>
                            </span>
                        </el-col>
                    </el-row>
                    <el-row :gutter="20">
                        <el-col :span="6" :offset="6">
                            <span class="Arrow">
                                <el-icon :size="50">
                                    <ArrowDownBold />
                                </el-icon>
                            </span>
                        </el-col>
                        <el-col :span="6" :offset="6">
                            <span class="Arrow">
                                <el-icon :size="50">
                                    <ArrowDownBold />
                                </el-icon>
                            </span>
                        </el-col>
                    </el-row>
                </div>

            </el-col>
            <el-col :span="8">
                <div>
                    <el-divider content-position="center">
                        <span>Gripper Control</span>
                    </el-divider>

                </div>
                <div class="gripper_control">
                    <el-row :gutter="20">
                        <el-col :span="6" :offset="6">
                            <span class="Arrow">
                                <el-icon :size="50">
                                    <ArrowUpBold />
                                </el-icon>
                            </span>
                        </el-col>
                        <el-col :span="6" :offset="6">
                            <span class="Arrow">
                               
                            </span>
                        </el-col>
                    </el-row>
                    <el-row :gutter="20">
                        <el-col :span="6">
                            <span class="Arrow">
                                <el-icon :size="50">
                                    <ArrowLeftBold />
                                </el-icon>
                            </span>
                        </el-col>
                        <el-col :span="6" :offset="6">
                            <span class="Arrow">
                                <el-icon :size="50">
                                    <ArrowRightBold />
                                </el-icon>
                            </span>
                        </el-col>
                    </el-row>
                    <el-row :gutter="20">
                        <el-col :span="6" :offset="6">
                            <span class="Arrow">
                                <el-icon :size="50">
                                    <ArrowDownBold />
                                </el-icon>
                            </span>
                        </el-col>
                        <el-col :span="6" :offset="6">
                            <span class="Arrow">
                                
                            </span>
                        </el-col>
                    </el-row>
                </div>

            </el-col>
        </el-row>

    </div>
</template>

<script>
import { dataType } from 'element-plus/es/components/table-v2/src/common';

export default {
    name: 'Jog',
    props: {
        msg: String,
        page_id: String
    },

    data() {

        return{

            value1: true,
        }
    }
    
}
</script>

<style>
.el-row {
    margin-bottom: 20px;
}

.el-row:last-child {
    margin-bottom: 0;
}

.el-col {
    border-radius: 4px;
}

.grid-content {
    border-radius: 4px;
    min-height: 36px;
}

.jog {

    padding-left: 30px;
    padding-right: 30px;
}

.head_jog {
    text-align: center;
    padding-left: 30px;
    padding-right: 30px;
}


el-col {

    text-align: left;
}

p {
    text-align: left;
}

.slider-demo-block {
    display: flex;
    align-items: left;
}

.slider-demo-block .el-slider {
    margin-top: 0;
    margin-left: 12px;
}

.slider-demo-block .demonstration {
    font-size: 14px;
    color: var(--el-text-color-secondary);
    line-height: 44px;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-bottom: 0;
}

.slider-demo-block .demonstration+.el-slider {
    flex: 0 0 70%;
}


.Arrow {
    text-align: center;
}


.pipette_control {
    padding-top: 30px;
    padding-left: 30px;
}

.gripper_control {
    padding-top: 30px;
    padding-left: 30px;
}

.listenning_switch {
    padding-top: 10px;
    padding-bottom: 10px;
}

p {
    text-align: left;
    color: #2c3e50;

  }

.jogging_parameter{
    margin-left: 10px;
    margin-right: 10px;
}
</style>

