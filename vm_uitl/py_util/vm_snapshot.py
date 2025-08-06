#rem 克隆前创建唯一快照，删除虚拟机时候删除虚拟机，并删除唯一快照
#vmrun -T ws snapshot   !TEMPLATE_PATH!\macos10.12.vmx  macos10.12_VM_!next_num!_snapshot
#	vmrun -T ws clone  !TEMPLATE_PATH!\macos10.12.vmx  !VM_DIR!\macos10.12_VM_!next_num!.vmx  linked  -snapshot=macos10.12_VM_!next_num!_snapshot
#
#