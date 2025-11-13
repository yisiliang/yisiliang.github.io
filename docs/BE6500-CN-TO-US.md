

# GL-iEnt GL-BE6500 国区到美区
# Converting GL-iNet BE6500 from CN to US(Global)


## 1. 找到地区码位置(Find the location of the region code CN)

```
bash-3.2$ hexdump -C /dev/mtdblock11

00000070  47 4c 2d 32 35 31 30 30  37 31 30 32 35 32 35 ff  |GL-251007102525.|
00000080  ff ff ff ff ff ff ff ff  55 53 0a ff ff ff ff ff  |........CN......|
00000090  ff ff ff ff ff ff ff ff  ff ff ff ff ff ff ff ff  |................|
```
## 2. 替换成US(Replace with US)
```
bash-3.2$ echo "US" | dd of=/dev/mtdblock11 bs=1 seek=136
bash-3.2$ hexdump -C /dev/mtdblock11

00000070  47 4c 2d 32 35 31 30 30  37 31 30 32 35 32 35 ff  |GL-251007102525.|
00000080  ff ff ff ff ff ff ff ff  55 53 0a ff ff ff ff ff  |........US......|
00000090  ff ff ff ff ff ff ff ff  ff ff ff ff ff ff ff ff  |................|
```
## 3. 重启(Reboot)
```
bash-3.2$ sync
bash-3.2$ reboot
```
