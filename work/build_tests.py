import struct
def ins(op,A=0,B=0,C=0,D=0): return bytes([op,A,B,C])+struct.pack('<i',D)
def proto(numparams,isvararg,maxstack,upvals,consts,instrs,protos=b''):
    o  = struct.pack('<I',numparams)+bytes([isvararg])+struct.pack('<I',maxstack)
    o += struct.pack('<I',len(upvals))
    for f,v in upvals: o += bytes([f])+struct.pack('<I',v)
    o += struct.pack('<I',len(consts))
    for t,v in consts:
        if   t==0: o += bytes([0])
        elif t==1: o += bytes([1,1 if v else 0])
        elif t==2: o += bytes([2])+struct.pack('<d',v)
        elif t==3: o += bytes([3])+struct.pack('<I',len(v))+v.encode()
        elif t==4: o += bytes([4])+struct.pack('<I',v)
    o += struct.pack('<I',len(instrs))
    for i in instrs: o += ins(*i)
    o += struct.pack('<I',1 if protos else 0)+protos
    return o

# --- чанк 1: 40+ инструкций, покрывающих ~30 опкодов ---
k1 = [(3,"alpha"),(3,"beta"),(3,"x"),(3,"print"),(3,"|"),(2,1.0)]
c1 = [
 (245,0),          # NEWTABLE r0
 (31,1,0,0,0),     # r1 = "alpha"
 (15,0,1),         # append r0,r1
 (31,1,0,0,1),     # r1 = "beta"
 (15,0,1),         # append r0,r1
 (144,2,0),        # r2 = #r0
 (24,3,0,5),       # r3 = concat(r0,"|")
 (31,4,0,0,2),     # r4 = "x"
 (39,5,3,4),       # r5 = r3..r4
 (33,6,3,3),       # r6 = r3*r3   (string*string -> ошибка!) заменим ниже
]
# правка: избегаем string*string — используем числа
c1[9] = (234,6,7)      # r6 = 7
c1 += [
 (33,6,6,6),       # r6 = r6*r6 = 49
 (208,7,6,0,5),    # r7 = r6 + 1.0 = 50
 (134,8,7),        # r8 = tostring(r7)
 (234,40,2),(234,41,6),(150,9,5,40),   # r40=2,r41=6 ; r9 = sub(r5,2,6)
 (234,11,65),(234,12,66),(253,10,11,12),   # r10 = char(65,66) = "AB"
 (162,13,11,12),   # r13 = bxor(65,66) = 3
 (145,14,11,12),   # r14 = band = 64
 (17,15,11,12),    # r15 = bor  = 67
 (242,16,11),      # r16 = bnot(65) = -66
 (10,17,11,1),     # r17 = lshift(65,1) = 130
 (166,18,11,1),    # r18 = rshift(65,1) = 32
 (83,19,11,11),    # r19 = (65==65) -> true
 (99,20,11,12),    # r20 = (65<66)  -> true
 (117,21,16),      # r21 = sign(-66) = -1
 (245,30),         # NEWTABLE r30
 (134,31,2),(15,30,31),    # tostring(#t)= "2"
 (134,31,7),(15,30,31),    # "50"
 (134,31,5),(15,30,31),    # "alphabeta|x"
 (15,30,9),                # "lphab"
 (15,30,10),               # "AB"
 (134,31,13),(15,30,31),   # "3"
 (134,31,14),(15,30,31),   # "64"
 (134,31,15),(15,30,31),   # "67"
 (134,31,16),(15,30,31),   # "-66"
 (134,31,17),(15,30,31),   # "130"
 (134,31,18),(15,30,31),   # "32"
 (134,31,19),(15,30,31),   # "true"
 (134,31,20),(15,30,31),   # "true"
 (134,31,21),(15,30,31),   # "-1"
 (24,32,30,5),             # r32 = concat(r30,"|")
 (133,33,0,0,3),           # r33 = print
 (188,33,2,0),             # print(r34)?? -> нужен arg в r34
 (138,0,0)]
# аргумент вызова должен лежать в A+1 = r34
c1[-3] = (91,34,32)  # MOVE r34 = r32
chunk1 = proto(0,0,40,[],k1,c1)

# --- чанк 2: замыкание с upvalue-регистром ---
child = proto(0,0,4,[(1,0)],[(2,1.0)],[(14,0,0),(208,0,0,0,0),(138,0,1)])
c2 = [(31,0,0,0,2),(214,1,0,0,0),(188,1,1,0),(91,3,1),(133,2,0,0,1),(188,2,2,0),(138,0,0)]
k2 = [(4,0),(3,"print"),(2,41.0)]
chunk2 = proto(0,0,8,[],k2,c2,child)

# --- чанк 3: неизвестный опкод 250 не должен ломать исполнение ---
c3 = [(31,0,0,0,0),(250,5,5,5,5),(133,1,0,0,1),(91,2,0),(188,1,2,0),(138,0,0)]
chunk3 = proto(0,0,4,[],[(3,"chunk with unknown opcode 250 executed fine"),(3,"print")],c3)

# --- чанк 4: math.z2 не существует ---
chunk4 = proto(0,0,4,[],[(2,2.0),(2,8.0)],[(31,0,0,0,0),(31,1,0,0,1),(243,2,0,1),(138,0,0)])

for i,c in enumerate([chunk1,chunk2,chunk3,chunk4],1):
    open('chunk%d.bin'%i,'wb').write(c)
print("chunks rebuilt")
