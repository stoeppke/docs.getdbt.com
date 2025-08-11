function Meta(meta)
  -- Store the source file in a global variable
  if meta.sourcefile then
    GLOBAL_SOURCE_FILE = meta.sourcefile
  end
  return meta
end

function Block(el)
  if el.t == "Header" and el.level == 1 and GLOBAL_SOURCE_FILE then
    -- Get the source file from metadata
    local source_file = pandoc.utils.stringify(GLOBAL_SOURCE_FILE)
    
    -- Convert file path to URL path  
    local url_path = source_file:gsub('^website/docs/', ''):gsub('%.mdx?$', '')
    local url = 'https://docs.getdbt.com/' .. url_path
    
    -- Create a styled link
    local link_text = 'View online: ' .. url
    local link = pandoc.Link(pandoc.Str(link_text), url)
    local para = pandoc.Para({pandoc.Str('Source: '), link})
    
    -- Add some spacing and return both header and source link
    return {el, pandoc.Para({}), para, pandoc.Para({})}
  end
  return el
end