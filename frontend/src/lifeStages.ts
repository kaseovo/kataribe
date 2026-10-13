/** Life stages are stored as extraction names them, in Japanese, whatever
 *  language the person speaks. The pages that show them are in English, so a
 *  judge's own family page does not open on 子供時代. */
const LIFE_STAGES: Record<string, string> = {
  子供時代: 'Childhood',
  学校: 'School years',
  仕事: 'Work',
  結婚: 'Marriage',
  子育て: 'Raising children',
  晩年: 'Later years',
};

export const lifeStage = (stored: string): string => LIFE_STAGES[stored] ?? stored;
