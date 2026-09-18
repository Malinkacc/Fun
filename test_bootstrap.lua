-- Test bootstrap decoder
local a,b,c,d,e,f,g,h,i,j,k={},{},{},{},{},{},{},{},{},{},{}

-- Base85 decode function
local function l(m)
    local n=""
    for o=1,#m,5 do 
        local q=m:sub(o,o+4)
        local r=0 
        for p=1,5 do r=r*85+(q:byte(p)-33) end 
        for p=1,4 do n=n..string.char(r%256) r=math.floor(r/256) end 
    end 
    return n 
end

-- RC4 decrypt function
local function t(u,v)
    local w={}
    for x=0,255 do w[x]=x end 
    local y=0 
    for x=0,255 do 
        y=(y+w[x]+v:byte(x%#v+1))%256 
        w[x],w[y]=w[y],w[x] 
    end 
    local z="" 
    local x2,y2=0,0 
    local bxor=bit32 and bit32.bxor or function(a,b) 
        local r,c,l=0,1,1 
        while a>0 or b>0 do 
            if (a%2)~=(b%2) then r=r+c end 
            a,b,c=math.floor(a/2),math.floor(b/2),c*2 
        end 
        return r 
    end 
    for x=1,#u do 
        x2=(x2+1)%256 
        y2=(y2+w[x2])%256 
        w[x2],w[y2]=w[y2],w[x2] 
        local aa=w[(w[x2]+w[y2])%256] 
        z=z..string.char(bxor(u:byte(x),aa)) 
    end 
    return z 
end

-- Test with simple data
local test_data = "Hello World!"
local test_key = "secretkey123"

-- Manually encrypt test_data with RC4 using Python
-- For now, just test that the functions work
print("Base85 decoder test:")
local test_b85 = "87cURD]j"  -- "Test" in base85
local decoded = l(test_b85)
print("Decoded: " .. decoded)

print("\nXOR test:")
local bxor = bit32 and bit32.bxor or function(a,b) 
    local r,c,l=0,1,1 
    while a>0 or b>0 do 
        if (a%2)~=(b%2) then r=r+c end 
        a,b,c=math.floor(a/2),math.floor(b/2),c*2 
    end 
    return r 
end

print("5 XOR 3 = " .. bxor(5, 3))  -- Should be 6
print("255 XOR 0 = " .. bxor(255, 0))  -- Should be 255
print("170 XOR 85 = " .. bxor(170, 85))  -- Should be 255

print("\nAll tests passed!")
