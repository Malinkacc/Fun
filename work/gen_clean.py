import re
src = open('orig_code.lua', encoding='utf-8').read()
src = re.sub(r'-- \(op\d+\)[^\n]*', '', src)
# вырезаем только "движок": q1, h4, c1, C4, W4, w4
parts = []
for fn in ['q1','h4','c1','C4','W4','w4']:
    m = re.search(r'local function %s\(.*?\n' % fn + r'(?=local function |local BLOB)', src, re.S)
    parts.append(m.group(0))
engine = "".join(parts)

RENAME = {
 'Q4':'strByte','v4':'strSub','P4':'strChar','e4':'tinsert','E1':'unpack','Y4':'bxor32','I4':'SHUFFLE','H4':'joinChunks',
 'q1':'decryptBlob','y4':'data','O4':'pos','C1':'shuffled','y1':'plain','n4':'blobLen','r4':'body','j1':'srcPos',
 'z4':'block','V4':'slot','h4':'readU32','c1':'readI32','C4':'readF64','s4':'b1','d1':'b2','b5':'b3','d4':'b4',
 'Q2':'b5','b4':'b6','h3':'b7','b3':'b8','q2':'sign','x2':'expBits','u2':'mant','O2':'val',
 'W4':'deserialize','w4':'runProto','i4':'proto','x1':'args','w1':'upvals','N4':'regs','k4':'code','f1':'consts',
 'B1':'env','D4':'pc','s1':'ins','k1':'op','u4':'A','p4':'B','L4':'C','m4':'D','M4':'varargs','a5':'unused1',
 'l1':'i','n1':'p','G1':'numParams','K1':'isVararg','L1':'maxStack','M1':'upvalDescs','R1':'fromReg','d2':'index',
 'H1':'consts_','o2':'instrs','T1':'protos','P2':'op_','J4':'A_','T4':'B_','l4':'C_','f4':'D_','e1':'protoOut',
 'A4':'blob','q4':'key_ignored','o1':'chunks','A1':'out','G4':'raw','U4':'val_','g4':'flag','S4':'idx','a1':'tag',
 'c4':'num','x4':'len_','v1':'nInstr','Z1':'instr','K4':'nProtos','B4':'nop1','O1':'nop2','J1':'nop3','F1':'nop4',
 'P1':'nop5','h1':'nop6','I1':'nop7','N1':'nop8','Q1':'nop9','F2':'_f2','g2':'_g2','f2':'_f2r','E4':'_tbl','J4_':'A__',
}
names = sorted(RENAME, key=len, reverse=True)
pat = re.compile(r'\b(%s)\b' % '|'.join(names))
clean = pat.sub(lambda m: RENAME[m.group(1)], engine)
open('vm_clean.lua','w').write(clean)
print("vm_clean.lua:", len(clean), "байт")
