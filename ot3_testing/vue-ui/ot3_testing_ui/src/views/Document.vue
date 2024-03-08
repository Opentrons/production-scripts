<template>
  <div class="head_sop">
    <h3>测试指导手册-调试专用</h3>
  </div>

  <div class="collapse_sop">
    <el-collapse accordion>
      <el-collapse-item title="1. OT3 Debuging Command" name="1">

        <el-timeline>
          <el-timeline-item center timestamp="jogging" placement="top">
            <el-card>
              <h4>1. jog pipette</h4>
              <p>python3 -m hardware_testing.examples.jog_ot3 --mount right</p>
              <h4>2. jog gripper</h4>
              <p>python3 -m hardware_testing.examples.jog_ot3 --mount gripper</p>
              <h4>3. run ot3repl</h4>
              <p>python3 -m opentrons.hardware_control.scripts.repl</p>
            </el-card>
          </el-timeline-item>
          <el-timeline-item timestamp="listenning sensor" placement="top">
            <el-card>
              <h4>1. listenning cap</h4>
              <p>python3 -m opentrons_hardware.scripts.monitor_sensors -m left -s capacitive</p>
            </el-card>
          </el-timeline-item>
          <el-timeline-item timestamp="require hardware" placement="top">
            <el-card>
              <h4>1. 烧录移液器条码</h4>
              <p>python3 -m opentrons_hardware.scripts.provision_pipette -w left</p>
              <h4>2. 查询机器固件</h4>
              <p>python3 -m opentrons_hardware.scripts.can_control</p>
            </el-card>
          </el-timeline-item>

          <el-timeline-item timestamp="flashing" placement="top">
            <el-card>
              <h4>1. 上传固件文件</h4>
              <p>python3 -m opentrons_hardware.scripts.provision_pipette -w left</p>
              <h4>2. 烧录Z轴</h4>
              <p>python3 -m opentrons_hardware.scripts.update_fw --target head --file
                /data/firmware-applications-v5/head-c2.hex</p>
              <h4>3. 烧录X轴</h4>
              <p>python3 -m opentrons_hardware.scripts.update_fw --target gantry-x --file
                /data/firmware-applications-v5/gantry-x-c1.hex</p>
              <h4>4. 烧录Y轴</h4>
              <p>python3 -m opentrons_hardware.scripts.update_fw --target gantry-y --file
                /data/firmware-applications-v5/gantry-y-c1.hex</p>
              <h4>5. 烧录pipette</h4>
              <p>python3 -m opentrons_hardware.scripts.update_fw --target pipette-left --file
                /data/firmware-applications-v5/pipettes-single-c2.hex</p>

            </el-card>
          </el-timeline-item>

          <el-timeline-item timestamp="2024/1/30" placement="top">
            last change date
          </el-timeline-item>
        </el-timeline>

      </el-collapse-item>

      <el-collapse-item title="2. OT3 Test Command" name="2">

        <el-timeline>
          <el-timeline-item center timestamp="Z-Stage Lifetime Test (Z轴老化测试)" placement="top">
            <el-card>
              <h4>1. ssh 登录</h4>
              <p>ssh root@192.168.6.xxx</p>
              <h4>2-a. 前台运行命令</h4>
              <p>python3 -m hardware_testing.scripts.force_pick_up_test --cycles 10000 --speed 10 --current 0.55</p>
              <h4>2-b. 后台运行命令</h4>
              <p>nohup python3 -m hardware_testing.scripts.force_pick_up_test --cycles 10000 --speed 5 --current 0.3 > /data/testing_data/output_life_z_stage.txt &</p>
              
            </el-card>
          </el-timeline-item>

          <el-timeline-item center timestamp="96CH Pick Up Lifetime Test (96通道老化测试)" placement="top">
            <el-card>
              <h4>1. ssh 登录</h4>
              <p>ssh root@192.168.6.xxx</p>
              <h4>2. 前台运行命令</h4>
              <p>python3 -m hardware_testing.scripts.tip_pick_up_96ch_lifetime --pick_up_num 417 --load_cal</p>
              <h4>3. 后台运行命令</h4>
              <p>nohup python3 -m hardware_testing.scripts.tip_pick_up_96ch_lifetime --pick_up_num 417 --load_cal > /data/testing_data/pick_up_lifetime.txt &</p>
            </el-card>
          </el-timeline-item>

          <el-timeline-item center timestamp="96CH Diagnostic Test (96诊断测试)" placement="top">
            <el-card>
              <h4>1. ssh 登录</h4>
              <p>ssh root@192.168.6.xxx</p>
              <h4>2. 运行命令</h4>
              <p>python3 -m hardware_testing.production_qc.ninety_six_assembly_qc_ot3</p>
              <h4>3. 运行命令 - 只测取针管漏液</h4>
              <p>python3 -m hardware_testing.production_qc.ninety_six_assembly_qc_ot3 --only-droplets</p>
              <h4>4. 运行命令 - 只测是否针管探测</h4>
              <p>python3 -m hardware_testing.production_qc.ninety_six_assembly_qc_ot3 --only-tip-sensor</p>
              <h4>5. 运行命令 - 只测针管压力</h4>
              <p>python3 -m hardware_testing.production_qc.ninety_six_assembly_qc_ot3 --only-pressure</p>
              <h4>6. 运行命令 - 只测电容</h4>
              <p>python3 -m hardware_testing.production_qc.ninety_six_assembly_qc_ot3 --only-capacitance</p>
              
            </el-card>
          </el-timeline-item>

          <el-timeline-item timestamp="2024/1/30" placement="top">
            last change date
          </el-timeline-item>
        </el-timeline>

      </el-collapse-item>
      <el-collapse-item title="Feedback" name="3">
        <div>
          Operation feedback: enable the users to clearly perceive their
          operations by style updates and interactive effects;
        </div>
        <div>
          Visual feedback: reflect current state by updating or rearranging
          elements of the page.
        </div>
      </el-collapse-item>
      <el-collapse-item title="Efficiency" name="4">
        <div>
          Simplify the process: keep operating process simple and intuitive;
        </div>
        <div>
          Definite and clear: enunciate your intentions clearly so that the
          users can quickly understand and make decisions;
        </div>
        <div>
          Easy to identify: the interface should be straightforward, which helps
          the users to identify and frees them from memorizing and recalling.
        </div>
      </el-collapse-item>
      <el-collapse-item title="Controllability" name="5">
        <div>
          Decision making: giving advices about operations is acceptable, but do
          not make decisions for the users;
        </div>
        <div>
          Controlled consequences: users should be granted the freedom to
          operate, including canceling, aborting or terminating current
          operation.
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<style scoped>
.collapse_sop {
  padding-left: 40px;
  padding-right: 40px;
}

h3 {
  padding-left: 40px;
}
</style>