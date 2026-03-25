-- File : sd.lua
-- Who  : Jose Amores
-- What : SD-over-SOMEIP dissector, called heuristically from SOMEIP

-- bitwise ops helpers
local band,bor = bit.band,bit.bor
local lshift, rshift = bit.lshift,bit.rshift
local tohex = bit.tohex

-- SD protocol
local p_my_some_ip_sd = Proto("my_some_ip_sd","my_some_ip Service Discovery")

local f_flags       	= ProtoField.uint8("my_some_ip.sd.flags","Flags",base.HEX)
local f_flags_reboot	= ProtoField.uint8("my_some_ip.sd.flags.reboot","Reboot",base.HEX,nil,0x80)
local f_flags_uni		= ProtoField.uint8("my_some_ip.sd.flags.unicast","Unicast",base.HEX,nil,0x40)
local f_res         	= ProtoField.uint24("my_some_ip.sd.res","Reserved",base.HEX)
local f_ents_len    	= ProtoField.uint32("my_some_ip.sd.len_ent","LenghtEntries",base.HEX)
local f_ents        	= ProtoField.bytes("my_some_ip.sd.ent","EntriesArray", base.NONE)
local f_opts_len    	= ProtoField.uint32("my_some_ip.sd.len_opt","LenghtOptions",base.HEX)
local f_opts        	= ProtoField.bytes("my_some_ip.sd.opt","OptionsArray", base.NONE)

p_my_some_ip_sd.fields = {f_flags,f_flags_reboot,f_flags_uni,f_res,f_ents_len,f_ents,f_opts_len,f_opts}

-- fields functions
local function my_some_ip_field_flag(subtree,buf)
	local f_subtree = subtree:add(f_flags,buf(0,1))
	f_subtree:add(f_flags_reboot,buf(0,1))
	f_subtree:add(f_flags_uni,buf(0,1))
end

function p_my_some_ip_sd.dissector(buf,pinfo,root)
    pinfo.cols.protocol = "SOME-IP/SD"

    -- create subtree
    local subtree = root:add(p_my_some_ip_sd,buf(0))

    -- add protocol fields to subtree
    --
    local offset = 0
    
    -- Flags
	my_some_ip_field_flag(subtree,buf(offset,1))
    offset = offset+1
    -- Reserved
    subtree:add(f_res,buf(offset,3))
    offset = offset+3

    -- Entries length
    local e_len = buf(offset,4):uint()
    subtree:add(f_ents_len,buf(offset,4))
    offset = offset+4
    -- Entries
    local my_some_ip_e_tree = subtree:add(f_ents,buf(offset,e_len))
	my_some_ip_e_tree:set_text("EntriesArray")
    --e_tree = subtree:add("EntriesArray")
    Dissector.get("my_some_ip_sd_entries"):call(buf(offset-4):tvb(),pinfo,my_some_ip_e_tree)
    offset = offset + e_len

    -- Options length
    local o_len = buf(offset,4):uint()
    subtree:add(f_opts_len,buf(offset,4))
    offset = offset+4
    -- Options
    local my_some_ip_o_tree = subtree:add(f_opts,buf(offset,o_len))
	my_some_ip_o_tree:set_text("OptionsArray")
    --o_tree = subtree:add("OptionsArray")
    Dissector.get("my_some_ip_sd_options"):call(buf(offset-4):tvb(),pinfo,my_some_ip_o_tree)
    offset = offset + o_len

end
