-- File : sd_entries.lua
-- Who  : Jose Amores 
-- What : SD subdissector in charge of parsing Entries within at EntriesArray
--
local p_my_some_ip_sd_entries = Proto("my_some_ip_sd_entries","my_some_ip_sd_entry")

-- sd message types
local my_some_ip_sd_entry_types = {
    [0] = "FIND_SERVICE",   -- 0x00
    [1] = "OFFER_SERVICE",  -- 0x01
    [6] = "SUBSCRIBE",      -- 0x06
    [7] = "SUBSCRIBE_ACK"   -- 0x07
}

local f_e_type      = ProtoField.uint8("my_some_ip.sd.e.type","Type",base.HEX,my_some_ip_sd_entry_types)
local f_e_o1_i      = ProtoField.uint8("my_some_ip.sd.e.opt1_i","Index 1st options",base.HEX)
local f_e_o2_i      = ProtoField.uint8("my_some_ip.sd.e.opt2_i","Index 2nd options",base.HEX)
local f_e_o1_n      = ProtoField.uint8("my_some_ip.sd.e.opt1_n","# opt 1",base.HEX,nil,0xf0)
local f_e_o2_n      = ProtoField.uint8("my_some_ip.sd.e.opt2_n","# opt 2",base.HEX,nil,0x0f)
local f_e_srv_id    = ProtoField.uint16("my_some_ip.sd.e.srv_id","Service ID",base.HEX)
local f_e_inst_id   = ProtoField.uint16("my_some_ip.sd.e.inst_id","Instance ID",base.HEX)
local f_e_v_major   = ProtoField.uint8("my_some_ip.sd.e.v_major","MajorVersion",base.HEX)
local f_e_ttl       = ProtoField.uint24("my_some_ip.sd.e.ttl","TTL",base.DEC)
local f_e_v_minor   = ProtoField.uint32("my_some_ip.sd.e.v_minor","MinorVersion",base.HEX)
local f_e_res		= ProtoField.uint16("my_some_ip.sd.e.res","Reserved",base.HEX,nil,0xfff0)
local f_e_cnt       = ProtoField.uint16("my_some_ip.sd.e.cnt","Counter",base.DEC,nil,0x000f)
local f_e_egrp_id  	= ProtoField.uint16("my_some_ip.sd.e.egrp_id","EventGroup_ID",base.HEX)

p_my_some_ip_sd_entries.fields = {f_e_type,f_e_o1_i,f_e_o2_i,f_e_o1_n,f_e_o2_n,f_e_srv_id,f_e_inst_id,f_e_v_major,f_e_ttl,f_e_v_minor,f_e_res,f_e_cnt,f_e_egrp_id}

local my_some_ip_parse_entries

function p_my_some_ip_sd_entries.dissector(buf,pinfo,root)
    local offset = 0

    -- length of EntriesArray
    local e_len = buf(offset,4):uint()
    offset = offset + 4

    -- parse entries  (NOTE : some extra variables to easen understanding)
    local e_len_parsed = 0
    while e_len_parsed < e_len do
        local i_parse = my_some_ip_parse_entries(root,buf(offset,(e_len-e_len_parsed)))
        e_len_parsed = e_len_parsed + i_parse
        offset = offset + i_parse
    end
end

local function my_some_ip_is_entry_service(type_u8)
    -- TODO : remove this magic numbers
    if ((type_u8 == 0x00) or (type_u8 == 0x01)) then
        return(true)
    else
        return(false)
    end
end

my_some_ip_parse_entries = function(subtree,buf)
    local offset = 0

    local e_subtree = subtree:add(p_my_some_ip_sd_entries, buf(offset,16))
    --Type
    local type_tree = e_subtree:add(f_e_type,buf(offset,1))
    local type_u8 = buf(offset,1):uint()
	e_subtree:append_text(" (" .. my_some_ip_sd_entry_types[type_u8]..")")
    offset = offset + 1

    -- Index 1st options
    e_subtree:add(f_e_o1_i,buf(offset,1))
    offset = offset + 1
    -- Index 2nd options
    e_subtree:add(f_e_o2_i,buf(offset,1))
    offset = offset + 1

    -- Num of opt 1 (NOTE : no increase in offset position, 4bit field)
    e_subtree:add(f_e_o1_n,buf(offset,1))
    -- Num of opt 2
    e_subtree:add(f_e_o2_n,buf(offset,1))
    offset = offset + 1

    -- ServiceID
    e_subtree:add(f_e_srv_id,buf(offset,2))
    offset = offset + 2
    -- InstanceID
    e_subtree:add(f_e_inst_id,buf(offset,2))
    offset = offset + 2

    -- Major version
    e_subtree:add(f_e_v_major,buf(offset,1))
    offset = offset + 1 
    -- TTL
    e_subtree:add(f_e_ttl,buf(offset,3))
    offset = offset + 3 

    -- SERVICE / EVENTGROUP entries
    if my_some_ip_is_entry_service(type_u8) then
        -- SERVICE
        -- Minor Version
        e_subtree:add(f_e_v_minor,buf(offset,4))
        offset = offset + 4
    else
        -- EVENTGROUP
		-- skip reserved
        e_subtree:add(f_e_res,buf(offset,2))
		-- Counter
        e_subtree:add(f_e_cnt,buf(offset,2))
        offset = offset + 2

        -- EventGroup ID
        e_subtree:add(f_e_egrp_id,buf(offset,2))
        offset = offset + 2
    end

    return(offset)
end

