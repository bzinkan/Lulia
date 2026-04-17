/**
 * wordTrie.js — Client-side word validation for Word Scramble.
 *
 * Builds a compact trie from the SOWPODS word list (~267K words).
 * Two public methods:
 *   isWord(word)   — exact match (returns boolean)
 *   isPrefix(prefix) — could this prefix lead to a valid word?
 *
 * The word list is fetched once from /data/sowpods.json (an array of
 * uppercase strings) and cached in a module-level singleton. Subsequent
 * calls to load() return the cached trie immediately.
 *
 * For the standalone preview HTML (no server), pass an array of words
 * directly to buildTrie() instead of using load().
 *
 * Trie node shape: { [char]: node, $: true? }
 *   — '$' marks end-of-word
 *   — child keys are single uppercase letters A-Z
 */

// Module-level cache
let _trie = null;
let _loading = null;

/**
 * Build a trie from an array of uppercase words.
 * @param {string[]} words
 * @returns {{ isWord: (w: string) => boolean, isPrefix: (p: string) => boolean }}
 */
export function buildTrie(words) {
  const root = {};
  for (const word of words) {
    let node = root;
    for (const ch of word) {
      if (!node[ch]) node[ch] = {};
      node = node[ch];
    }
    node.$ = true;
  }

  function walk(str) {
    let node = root;
    for (const ch of str.toUpperCase()) {
      if (!node[ch]) return null;
      node = node[ch];
    }
    return node;
  }

  return {
    isWord(w) {
      const node = walk(w);
      return node ? node.$ === true : false;
    },
    isPrefix(p) {
      return walk(p) !== null;
    },
  };
}

/**
 * Load the SOWPODS dictionary from the server and return a trie.
 * Cached — only fetches once. Safe to call from multiple components.
 *
 * @returns {Promise<{ isWord: (w: string) => boolean, isPrefix: (p: string) => boolean }>}
 */
export async function loadDictionary() {
  if (_trie) return _trie;
  if (_loading) return _loading;

  _loading = (async () => {
    try {
      const res = await fetch('/data/sowpods.json');
      if (!res.ok) throw new Error(`Failed to load dictionary: ${res.status}`);
      const words = await res.json();
      _trie = buildTrie(words);
      return _trie;
    } catch (err) {
      console.error('[wordTrie] Dictionary load failed, using fallback mini-dict', err);
      // Fallback: a small set of common words so the game isn't totally broken
      _trie = buildTrie(FALLBACK_WORDS);
      return _trie;
    } finally {
      _loading = null;
    }
  })();

  return _loading;
}

/**
 * Synchronous access — returns the cached trie or null if not yet loaded.
 */
export function getDictionary() {
  return _trie;
}

// ~500 common words as fallback if the full SOWPODS list can't load
const FALLBACK_WORDS = [
  'THE','AND','FOR','ARE','BUT','NOT','YOU','ALL','HER','WAS','ONE','OUR','OUT',
  'HAS','HAD','HOT','HAS','HIM','HIS','HOW','ITS','LET','MAY','NEW','NOW','OLD',
  'SEE','WAY','WHO','DID','GET','HAS','HIM','HIS','HOW','MAN','NEW','NOW','OLD',
  'OUR','OWN','SAY','SHE','TOO','USE','DAD','MOM','BOY','BIG','END','FAR','FEW',
  'GOT','HAS','HER','HIM','HIS','HOW','ITS','LET','MAY','MEN','NEW','OLD','OUR',
  'OWN','RAN','RED','RUN','SAT','SAW','SAY','SET','SIT','SIX','TEN','THE','TOP',
  'TRY','TWO','USE','WAR','YES','YET','CAT','DOG','MAP','PEN','SUN','CAR','BUS',
  'CUP','HAT','BED','BOX','BAG','KEY','ARM','LEG','EAR','EYE','LIP','TOE','RIB',
  'JAW','GUM','HIP','JAM','FIG','PIE','NUT','OAT','RYE','YAM','PEA','ALE','RUM',
  'GIN','TEA','ICE','OIL','INK','WAX','TIN','ORE','GEM','OAK','ELM','ASH','FIR',
  'THAT','WITH','THIS','HAVE','FROM','THEY','BEEN','SAID','EACH','MAKE','LIKE',
  'LONG','LOOK','MANY','SOME','THEM','THAN','CALL','COME','MADE','FIND','BACK',
  'ONLY','JUST','KNOW','TAKE','WANT','GIVE','MOST','ALSO','GOOD','MUCH','KEEP',
  'HELP','TELL','DOES','TURN','MOVE','LIVE','REAL','LEFT','SAME','LAST','READ',
  'NEED','HIGH','OPEN','PART','PLAY','WORD','WORK','YEAR','HOME','HAND','FREE',
  'TREE','FISH','BIRD','FROG','BEAR','DEER','WOLF','GOAT','LION','DUCK','WORM',
  'BOOK','PAGE','SONG','GAME','MATH','ARTS','BAND','CLUB','TEAM','SHIP','BOAT',
  'LAKE','POND','HILL','CAVE','ROCK','SAND','SNOW','RAIN','WIND','FIRE','STAR',
  'MOON','RING','BELL','DRUM','FLAG','LAMP','ROPE','TAPE','WIRE','PIPE','GEAR',
  'ABLE','ALSO','AREA','AWAY','BABY','BAKE','BALL','BASE','BATH','BEAT','BELL',
  'BEST','BLOW','BLUE','BODY','BOLD','BOMB','BONE','BORE','BORN','BOTH','BOWL',
  'BURN','BUSY','CALM','CAME','CAMP','CARD','CARE','CASE','CASH','CAST','CHAT',
  'CHIP','CITY','CLAY','CLIP','COAT','CODE','COLD','COOK','COOL','COPE','COPY',
  'CORD','CORE','COST','CREW','CROP','CURE','CUTE','DALE','DAME','DAMP','DARE',
  'DARK','DATA','DATE','DAWN','DEAD','DEAF','DEAL','DEAR','DEBT','DECK','DEEP',
  'DINE','DIRT','DISH','DISK','DOCK','DONE','DOOM','DOOR','DOSE','DOWN','DRAG',
  'DRAW','DREW','DROP','DRUM','DUAL','DULL','DUMB','DUMP','DUNE','DUST','DUTY',
  'EARN','EASE','EAST','EASY','EDGE','ELSE','EMIT','EVEN','EVER','EXAM','FACE',
  'FACT','FADE','FAIL','FAIR','FAKE','FALL','FAME','FARM','FAST','FATE','FEAR',
  'FEED','FEEL','FEET','FELL','FELT','FILE','FILL','FILM','FINE','FIRM','FIST',
  'FIVE','FLAG','FLAT','FLAW','FLED','FLEW','FLIP','FLOW','FOAM','FOLD','FOLK',
  'FOND','FOOD','FOOL','FOOT','FORD','FORE','FORK','FORM','FORT','FOUL','FOUR',
  'FROM','FUEL','FULL','FUND','FURY','FUSE','GAIN','GALE','GANG','GAZE','GIFT',
  'GLAD','GLOW','GLUE','GOAL','GOES','GOLD','GOLF','GONE','GRAB','GRAY','GREW',
  'GREY','GRID','GRIM','GRIN','GRIP','GROW','GULF','GUST','GUYS','HACK','HALF',
  'HALL','HALT','HANG','HARD','HARM','HATE','HAUL','HEAD','HEAL','HEAP','HEAR',
  'HEAT','HEEL','HELD','HERB','HERE','HERO','HIDE','HINT','HIRE','HOLD','HOLE',
  'HOLY','HOOK','HOPE','HORN','HOST','HUGE','HUNG','HUNT','HURT','HYMN','ICON',
  'IDEA','INCH','INTO','IRON','ISLE','ITEM','JACK','JAIL','JAZZ','JEAN','JEST',
  'JOBS','JOIN','JOKE','JUMP','JUNE','JURY','KEEN','KEPT','KICK','KIDS','KILL',
  'KIND','KING','KISS','KNEE','KNEW','KNIT','KNOB','KNOT','LACK','LAID','LANE',
  'LATE','LAWN','LEAD','LEAF','LEAN','LEAP','LEFT','LEND','LENS','LESS','LIAR',
  'LICK','LIED','LIES','LIFE','LIFT','LIMB','LIME','LINE','LINK','LIST','LOAD',
  'LOAN','LOCK','LOGO','LONE','LOOK','LORD','LOSE','LOSS','LOST','LOUD','LOVE',
  'LUCK','LUMP','LUNG','LURE','LURK','MAID','MAIL','MAIN','MALE','MALL','MALT',
  'MANE','MANY','MARK','MARS','MASK','MASS','MAST','MATE','MAZE','MEAL','MEAN',
  'MEAT','MEET','MELT','MEMO','MEND','MENU','MERE','MESH','MESS','MILD','MILE',
  'MILK','MILL','MIME','MIND','MINE','MINT','MISS','MIST','MOCK','MODE','MOLD',
  'MOOD','MORE','MOSS','MOST','MOTH','MUCH','MUSE','MUST','MYTH','NAIL','NAME',
  'NEAT','NECK','NEST','NETS','NEWS','NEXT','NICE','NINE','NODE','NONE','NOON',
  'NORM','NOSE','NOTE','NOUN','NUDE','OATH','ODDS','OILS','OKAY','ONCE','ONES',
  'ONTO','OVEN','OVER','PACE','PACK','PACT','PAGE','PAID','PAIN','PAIR','PALE',
  'PALM','PANE','PARA','PARK','PASS','PAST','PATH','PEAK','PEAR','PEER','PILL',
  'PINE','PINK','PIPE','PLAN','PLAY','PLEA','PLOT','PLUG','PLUM','PLUS','POEM',
  'POET','POLE','POLL','POLO','POND','POOL','POOR','POPE','PORK','PORT','POSE',
  'POST','POUR','PRAY','PREY','PROP','PULL','PULP','PUMP','PUNK','PURE','PUSH',
  'QUIT','QUIZ','RACE','RACK','RAGE','RAID','RAIL','RAIN','RANK','RARE','RASH',
  'RATE','RAYS','READ','REAL','REAR','REEF','REIN','RELY','RENT','REST','RICH',
  'RIDE','RIFE','RIFT','RING','RIOT','RISE','RISK','ROAD','ROAM','ROBE','ROCK',
  'RODE','ROLE','ROLL','ROOF','ROOM','ROOT','ROPE','ROSE','RUIN','RULE','RUSH',
  'RUTH','SACK','SAFE','SAGE','SAKE','SALE','SALT','SAME','SAND','SANG','SANK',
  'SAVE','SEAL','SEAM','SEAT','SEED','SEEK','SEEM','SEEN','SELF','SELL','SEND',
  'SENT','SEPT','SHED','SHIN','SHIP','SHOP','SHOT','SHOW','SHUT','SICK','SIDE',
  'SIGH','SIGN','SILK','SING','SINK','SITE','SIZE','SKIP','SLAM','SLAP','SLID',
  'SLIM','SLIP','SLOT','SLOW','SNAP','SNOW','SOAK','SOAR','SOCK','SOFT','SOIL',
  'SOLD','SOLE','SOME','SONG','SOON','SORT','SOUL','SOUR','SPAN','SPIN','SPIT',
  'SPOT','SPUR','STAB','STEM','STEP','STIR','STOP','STUB','SUCH','SUIT','SURE',
  'SURF','SWAN','SWAP','SWIM','SWOP','TABS','TACK','TAIL','TAKE','TALE','TALK',
  'TALL','TAME','TANK','TAPE','TART','TASK','TEAR','TELL','TEND','TENT','TERM',
  'TEST','TEXT','THEM','THEN','THEY','THIN','TIDE','TIDY','TIED','TIER','TILE',
  'TILL','TILT','TIME','TINY','TIRE','TOAD','TOIL','TOLD','TOLL','TOMB','TONE',
  'TOOK','TOOL','TOPS','TORE','TORN','TOSS','TOUR','TOWN','TRAP','TRAY','TRIM',
  'TRIO','TRIP','TRUE','TUBE','TUCK','TUFT','TUNE','TURN','TWIN','TYPE','UGLY',
  'UNDO','UNIT','UPON','URGE','USED','USER','VALE','VANE','VARY','VAST','VEIN',
  'VENT','VERB','VERY','VEST','VETO','VIEW','VINE','VISA','VOID','VOLT','VOTE',
  'WADE','WAGE','WAIT','WAKE','WALK','WALL','WAND','WANT','WARD','WARM','WARN',
  'WARP','WARY','WASH','WAVE','WAVY','WEAK','WEAR','WEED','WEEK','WELL','WENT',
  'WERE','WEST','WHAT','WHEN','WHOM','WIDE','WIFE','WILD','WILL','WILT','WILY',
  'WIND','WINE','WING','WIPE','WIRE','WISE','WISH','WITH','WOKE','WOMB','WOOD',
  'WOOL','WORD','WORE','WORM','WORN','WRAP','YARD','YAWN','ZERO','ZONE','ZOOM',
  'AA','AB','AD','AE','AG','AH','AI','AL','AM','AN','AR','AS','AT','AW','AX','AY',
  'BA','BE','BI','BO','BY','DA','DE','DI','DO','ED','EF','EH','EL','EM','EN','ER',
  'ES','ET','EW','EX','FA','FE','GO','GU','HA','HE','HI','HM','HO','ID','IF','IN',
  'IO','IS','IT','JA','JO','KA','KI','LA','LI','LO','MA','ME','MI','MM','MO','MU',
  'MY','NA','NE','NO','NU','NY','OB','OD','OE','OF','OH','OI','OK','OM','ON','OO',
  'OP','OR','OS','OU','OW','OX','OY','PA','PE','PI','PO','QI','RE','SH','SI','SO',
  'ST','TA','TE','TI','TO','UG','UH','UM','UN','UP','UR','US','UT','WE','WO','XI',
  'XU','YA','YE','YO','ZA','ZO',
];
