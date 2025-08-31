# 🧠 Smart Event Creation with Natural Language

The Event Management system now supports **intelligent natural language parsing** for dates and times! You can create events using everyday language instead of complex date formats.

## 🎯 Examples You Can Use

### **Today & Tomorrow**
- `today 8pm` → Today at 8:00 PM
- `tonight` → Today at 8:00 PM  
- `today at 3:30pm` → Today at 3:30 PM
- `tomorrow 7pm` → Tomorrow at 7:00 PM
- `tomorrow at 2:30` → Tomorrow at 2:30 PM

### **Day Names**
- `friday 8pm` → Next Friday at 8:00 PM
- `next monday 3pm` → Next Monday at 3:00 PM
- `saturday at noon` → Next Saturday at 12:00 PM
- `this thursday 7:30pm` → This Thursday at 7:30 PM

### **Specific Dates**
- `jan 15 8pm` → January 15th at 8:00 PM
- `march 3rd 7:30pm` → March 3rd at 7:30 PM
- `12/25 6pm` → December 25th at 6:00 PM
- `december 31st 11:59pm` → December 31st at 11:59 PM

### **Relative Time**
- `in 2 hours` → 2 hours from now
- `in 30 minutes` → 30 minutes from now
- `in 1 day` → 1 day from now

### **Time Only** (applies to today)
- `8pm` → Today at 8:00 PM
- `3:30pm` → Today at 3:30 PM
- `noon` → Today at 12:00 PM
- `midnight` → Today at 12:00 AM

### **Special Times**
- `morning` → Today at 9:00 AM
- `afternoon` → Today at 2:00 PM
- `evening` → Today at 6:00 PM
- `night` → Today at 8:00 PM

### **Traditional Formats** (still supported)
- `2024-12-25` → December 25, 2024 at 12:00 PM
- `12/25/2024 14:30` → December 25, 2024 at 2:30 PM
- `2024-01-15 20:00` → January 15, 2024 at 8:00 PM

## 🚀 How to Use

1. **Use `/create_event` command**
2. **For the date field, type naturally:**
   - Instead of: `2024-09-01 20:00`
   - Just type: `tomorrow 8pm`

3. **The bot understands and confirms:**
   - Shows you exactly when the event will be
   - Converts to proper date/time format
   - Validates it's in the future

## 💡 Smart Features

- **Context Aware**: "Friday" means next Friday, "morning" means today's morning
- **Flexible**: Works with or without "at", "on", punctuation
- **Intelligent**: Assumes evening times for events (1-7 → PM automatically)
- **Fallback**: Traditional formats still work if natural language fails

## ⚡ Quick Examples

```
/create_event name:"Team Meeting" description:"Weekly sync" date:"friday 3pm"
/create_event name:"Game Night" description:"Fun time!" date:"tomorrow 8pm" 
/create_event name:"Training" description:"New member training" date:"next monday 7pm"
```

The bot makes event creation **intuitive and fast** - no more struggling with date formats! 🎉
