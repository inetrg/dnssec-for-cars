-- File : sd_options.lua
-- Who  : Jose Amores
-- What : SD subdissector in charge of parsing Options within at OptionsArray

local p_my_some_ip_sd_options = Proto("my_some_ip_sd_options","my_some_ip_sd_option")

local MY_SOME_IP_O_TYPE_CFG        = 0x01
local MY_SOME_IP_O_TYPE_LB         = 0x02
local MY_SOME_IP_O_TYPE_IP4_EP     = 0x04
local MY_SOME_IP_O_TYPE_IP6_EP     = 0x06
local MY_SOME_IP_O_TYPE_IP4_MC     = 0x14
local MY_SOME_IP_O_TYPE_IP6_MC     = 0x16
local MY_SOME_IP_O_TYPE_IP4_SD_EP  = 0x24
local MY_SOME_IP_O_TYPE_IP6_SD_EP  = 0x26

local my_some_ip_o_types = {
    [MY_SOME_IP_O_TYPE_CFG]        = "CONFIGURATION",      -- 0x01
    [MY_SOME_IP_O_TYPE_LB]         = "LOAD_BALANCING",     -- 0x02
    [MY_SOME_IP_O_TYPE_IP4_EP]     = "IPv4_ENDPOINT",      -- 0x04
    [MY_SOME_IP_O_TYPE_IP6_EP]     = "IPv6_ENDPOINT",      -- 0x06
    [MY_SOME_IP_O_TYPE_IP4_MC]     = "IPv4_MULTICAST",     -- 0x14
    [MY_SOME_IP_O_TYPE_IP6_MC]     = "IPV6_MULTICAST",     -- 0x16
    [MY_SOME_IP_O_TYPE_IP4_SD_EP]  = "IPv4_SD_ENDPOINT",   -- 0x24
    [MY_SOME_IP_O_TYPE_IP6_SD_EP]  = "IPv6_SD_ENDPOINT"    -- 0x26
}
local my_some_ip_o_l4 = {
    [0x06]    = "TCP", -- 0x06
    [0x11]    = "UDP"  -- 0x11
}

local f_o_len       = ProtoField.uint16("my_some_ip.sd.o.len","Length",base.HEX)
local f_o_type      = ProtoField.uint8("my_some_ip.sd.o.type","Type",base.HEX,my_some_ip_o_types)
local f_o_cfg_str   = ProtoField.string("my_some_ip.sd.o.cfg_str","ConfigString") 
local f_o_prio      = ProtoField.uint16("my_some_ip.sd.o.prio","Priority") 
local f_o_weight    = ProtoField.uint16("my_some_ip.sd.o.weight","Weight") 
local f_o_res0		= ProtoField.uint8("my_some_ip.sd.o.res0","Reserved",base.HEX)
local f_o_ipv4      = ProtoField.ipv4("my_some_ip.sd.o.ipv4","IPv4") 
local f_o_ipv6      = ProtoField.ipv6("my_some_ip.sd.o.ipv6","IPv6")
local f_o_res1		= ProtoField.uint8("my_some_ip.sd.o.res1","Reserved",base.HEX)
local f_o_l4        = ProtoField.uint8("my_some_ip.sd.o.l4","L4-Protocol",base.HEX,my_some_ip_o_l4) 
local f_o_port      = ProtoField.uint16("my_some_ip.sd.o.port","Port") 

p_my_some_ip_sd_options.fields = {f_o_len,f_o_type,f_o_cfg_str,f_o_prio,f_o_weight,f_o_res0,f_o_ipv4,f_o_ipv6,f_o_res1,f_o_l4,f_o_port}

local my_some_ip_parse_options

function p_my_some_ip_sd_options.dissector(buf,pinfo,root)
    local offset = 0

    -- length of OptionsArray
    local o_len = buf(offset,4):uint()
    offset = offset + 4

    -- parse options (NOTE : some extra variables to easen understanding)
    local o_len_parsed = 0
    while o_len_parsed < o_len do
        local i_parse = my_some_ip_parse_options(root,buf(offset,(o_len-o_len_parsed)))
        o_len_parsed = o_len_parsed + i_parse 
        offset = offset + i_parse
    end
end

local function my_some_ip_is_type_ipv4(type_u8)
    return((type_u8 == MY_SOME_IP_O_TYPE_IP4_EP) or (type_u8 == MY_SOME_IP_O_TYPE_IP4_MC) or (type_u8 == MY_SOME_IP_O_TYPE_IP4_SD_EP))
end
local function my_some_ip_is_type_ipv6(type_u8)
    return((type_u8 == MY_SOME_IP_O_TYPE_IP6_EP) or (type_u8 == MY_SOME_IP_O_TYPE_IP6_MC) or (type_u8 == MY_SOME_IP_O_TYPE_IP6_SD_EP))
end

my_some_ip_parse_options = function(subtree,buf)
    local offset = 0
	
	local len_u16 = buf(offset,2):uint()
	-- SD option entry [len_u16 + 2 byte (length field) + 1 byte (type field)]
    local o_subtree = subtree:add(p_my_some_ip_sd_options,buf(offset,len_u16+2+1))

    -- Length
    o_subtree:add(f_o_len,buf(offset,2))
    offset = offset + 2

    -- Type
    local type_tree = o_subtree:add(f_o_type,buf(offset,1))
    local type_u8 = buf(offset,1):uint()
    offset = offset + 1
    if my_some_ip_o_types[type_u8] ~= nil then
        
        -- also update "root" with entry type
        o_subtree:append_text(" : "..my_some_ip_o_types[type_u8])
    end

    -- Reserved
	o_subtree:add(f_o_res0,buf(offset,1))
    offset = offset + 1
	-- decrement len_u16 accordingly
    len_u16 = len_u16 - 1

    -- switch and parse correct Option
    if (type_u8 == MY_SOME_IP_O_TYPE_CFG) then
        -- Config string
        local cfg_tree = o_subtree:add(f_o_cfg_str,buf(offset,len_u16))
        offset = offset + len_u16
    elseif (type_u8 == MY_SOME_IP_O_TYPE_LB) then
        -- Priority 
        o_subtree:add(f_o_prio,buf(offset,2))
        offset = offset + 2
        -- Weight
        o_subtree:add(f_o_weight,buf(offset,2))
        offset = offset + 2
    elseif my_some_ip_is_type_ipv4(type_u8) then
        -- IPv4
        o_subtree:add(f_o_ipv4,buf(offset,4))
        offset = offset + 4
    elseif my_some_ip_is_type_ipv6(type_u8) then
        -- IPv6
        o_subtree:add(f_o_ipv6,buf(offset,16))
        offset = offset + 16
    end

    -- IPv4, IPv6 common post-fields
    --
    if my_some_ip_is_type_ipv4(type_u8) or my_some_ip_is_type_ipv6(type_u8) then
        -- Reserved
		o_subtree:add(f_o_res1,buf(offset,1))
        offset = offset + 1

        -- L4-Proto
        local l4_tree = o_subtree:add(f_o_l4,buf(offset,1))
        local l4_u8 = buf(offset,1):uint()
        offset = offset +1

        -- Port
        o_subtree:add(f_o_port,buf(offset,2))
        offset = offset + 2
    end

    return(offset)
end
